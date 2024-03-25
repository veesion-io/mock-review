"""
This PR adds a new API route to the application.
The route allows updating the label and other info of a video decoded from its URL.
Please review the code and provide all possible feedback to improve it.
"""

import json
import os
from typing import Dict
from urllib.parse import urlparse
from uuid import UUID

from django.db import models
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods

THEFT_LABELS = ["theft", "Suspicious"]


class Location(models.Model):
    name = models.CharField(unique=True)
    total_theft = models.IntegerField(default=0)


class Alert_Label(models.Model):
    name = models.CharField(primary_key=True, unique=True, db_index=True)


class Video(models.Model):
    uuid = models.UUIDField(primary_key=True)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    alertlabelname = models.ForeignKey(Alert_Label, on_delete=models.SET_NULL, null=True)
    category = models.IntegerField(default=0)


def validate_uuid(uuid: UUID | str) -> str:
    """Validate and return a normalized UUID string."""
    if isinstance(uuid, UUID):
        return str(uuid).lower()

    try:
        return str(UUID(uuid)).lower()
    except Exception as exc:
        raise ValueError(f"Incorrect UUID format: {uuid}") from exc


def url_path_parse(url) -> Dict[str, str]:
    """Example url input: "http://example.com/location_name/extra/video_uuid-blurred.mp4"""
    url_parsed = urlparse(url)
    url_split = url_parsed.path.split("/")
    # remove empty strings
    url_split = list(filter(len, url_split))
    if "extra" in url_split:
        url_split.remove("extra")
    if len(url_split) < 2:
        raise Exception("incomplete url")

    try:
        location = url_split[-2]
        video_name = validate_uuid(os.path.splitext(url_split[-1])[0].rstrip("-blurred"))
    except Exception:
        raise Exception("not uuid url")

    return {"location": location, "video_name": video_name}


@require_http_methods(["PATCH"])
def update_label_from_url_view(request: HttpRequest, url: str, label_name) -> HttpResponse:
    if request.method == "PATCH":
        parsed_result: dict[str, str] = url_path_parse(url)
        location = parsed_result["location"]
        video_name = parsed_result["video_name"]
        try:
            video = Video.objects.get(pk=video_name).select_related("location")
        except Video.DoesNotExist:
            loc_obj, _ = Location.objects.get_or_create(name=location)
            video = Video.objects.create(uuid=video_name, location=loc_obj)

        if video.location.name != location:
            return HttpResponse(json.dumps({"errors": "mismatch location"}), status=404)
        else:
            try:
                label = Alert_Label.objects.get_or_create(name=label_name)
                video.alertlabelname = label[0]
                video.save()

                if label_name in THEFT_LABELS:
                    video.category = 1
                    video.location.total_theft += 1
                else:
                    video.category = 0
                video.save()
                video.location.save(update_fields=["total_theft"])
                return HttpResponse(json.dumps({"success": "label updated"}), status=200)
            except Exception:
                return HttpResponse(json.dumps({"errors": "error processing"}), status=500)
    else:
        return HttpResponse(json.dumps({"errors": "invalid method"}), status=405)
