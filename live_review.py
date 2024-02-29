import json
import os
from typing import Dict, Union
from urllib.parse import urlparse
from uuid import UUID

from django.db import models
from django.http import HttpRequest, HttpResponse

THEFT_LABELS = ["theft", "Suspicious"]


class Location(models.Model):
    uuid = models.UUIDField(primary_key=True)


class Label(models.Model):
    name = models.CharField(primary_key=True)


class Video(models.Model):
    uuid = models.UUIDField(primary_key=True)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    label = models.ForeignKey(Label, on_delete=models.SET_NULL, null=True)
    category = models.IntegerField(default=0)


def validate_uuid(uuid: Union[UUID, str]) -> str:
    """Validate and return a normalized UUID string."""
    if isinstance(uuid, UUID):
        return str(uuid).lower()

    try:
        return str(UUID(uuid)).lower()
    except Exception as exc:
        raise ValueError(f"Incorrect UUID format: {uuid}") from exc


def url_path_parse(url) -> Dict[str, str]:
    url_parsed = urlparse(url)
    url_split = url_parsed.path.split("/")
    # remove empty strings
    url_split = list(filter(len, url_split))
    if "more" in url_split:
        url_split.remove("more")
    if len(url_split) < 2:
        # Missing path
        raise Exception("incomplete url")

    try:
        location = validate_uuid(url_split[-2])
        video_name = validate_uuid(os.path.splitext(url_split[-1])[0].rstrip("-blurred"))
    except Exception:
        raise Exception("not uuid url")

    return {"location": location, "video_name": video_name}


def update_label_from_url_view(request: HttpRequest, url: str, label_name) -> HttpResponse:
    if request.method == "POST":
        parsed_result: dict[str, str] = url_path_parse(url)
        location = parsed_result["location"]
        video_name = parsed_result["video_name"]
        try:
            video = Video.objects.get(pk=video_name)
        except Video.DoesNotExist:
            video = Video.objects.create(uuid=video_name, location_id=location)

        if video.location.uuid != location:
            return HttpResponse(json.dumps({"errors": "mismatch location"}), status=404)
        else:
            try:
                label = Label.objects.get_or_create(name=label_name)
                video.label = label[0]
                video.save()

                if label_name in THEFT_LABELS:
                    video.category = 1
                else:
                    video.category = 0
                video.save()
                return HttpResponse(json.dumps({"success": "label updated"}), status=200)
            except Exception:
                return HttpResponse(json.dumps({"errors": "error processing"}), status=500)
    else:
        return HttpResponse(json.dumps({"errors": "invalid method"}), status=405)
