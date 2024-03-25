import json
import os
from typing import Dict
from urllib.parse import urlparse
from uuid import UUID

from django.db import models
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods

# inconsistent lowercase and uppercase
# inconsistent quote
THEFT_LABELS = ["theft", "Suspicious"]


class Location(models.Model):
    name = models.CharField(unique=True)
    total_theft = models.IntegerField(default=0)


# Debate: should we use CharField as primary key?
# Bad class naming: PascalCase
class Alert_Label(models.Model):
    # primary_key=True already implies unique=True and db_index=True
    name = models.CharField(primary_key=True, unique=True, db_index=True)


# Question: how to choose on_delete mode?
class Video(models.Model):
    uuid = models.UUIDField(primary_key=True)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    # Bad variable naming: snake_case
    alertlabelname = models.ForeignKey(Alert_Label, on_delete=models.SET_NULL, null=True)
    category = models.IntegerField(default=0)


# Inconsistent type hint: only valid from Python 3.9
def validate_uuid(uuid: UUID | str) -> str:
    """Validate and return a normalized UUID string."""
    if isinstance(uuid, UUID):
        return str(uuid).lower()

    try:
        return str(UUID(uuid)).lower()
    except Exception as exc:
        raise ValueError(f"Incorrect UUID format: {uuid}") from exc


# Inconsistent naming convention, verb first for method: parse_url_path
# Lack doc strings / comments => hard to understand => candidate should complain
def url_path_parse(url) -> Dict[str, str]:
    """Example url input: "http://example.com/location_name/extra/video_uuid-blurred.mp4"""
    url_parsed = urlparse(url)
    url_split = url_parsed.path.split("/")
    # remove empty strings
    url_split = list(filter(len, url_split))
    if "extra" in url_split:
        url_split.remove("extra")
    if len(url_split) < 2:
        # Missing 1 or 2 components
        # Should add log
        raise Exception("incomplete url")

    try:
        location = url_split[-2]
        # Nested method call => hard to understand
        # Utiliser pathlib
        video_name = validate_uuid(os.path.splitext(url_split[-1])[0].rstrip("-blurred"))
    except Exception:
        # Should add log
        # Raise exception inside except block without adding anything => useless
        raise Exception("not uuid url")

    # Could return tuple here
    return {"location": location, "video_name": video_name}


# no type hint for label_name
# POST method should get data from request.body instead of params
@require_http_methods(["PATCH"])
def update_label_from_url_view(request: HttpRequest, url: str, label_name) -> HttpResponse:
    # Invert if condition to reduce nested block
    if request.method == "PATCH":
        parsed_result: dict[str, str] = url_path_parse(url)
        location = parsed_result["location"]
        video_name = parsed_result["video_name"]
        try:
            video = Video.objects.get(pk=video_name).select_related("location")
        except Video.DoesNotExist:
            loc_obj, _ = Location.objects.get_or_create(name=location)
            video = Video.objects.create(uuid=video_name, location=loc_obj)

        # Extra DB hit => use select_related or prefetch_related
        if video.location.name != location:
            return HttpResponse(json.dumps({"errors": "mismatch location"}), status=404)
        # We can remove else here
        else:
            # try/except block too big => hard to narrow down the error
            # not atomic transactions
            try:
                label = Alert_Label.objects.get_or_create(name=label_name)
                video.alertlabelname = label[0]  # label is a tuple => inconsistent use of get_or_create
                video.save()  # should use updated_fields

                if label_name in THEFT_LABELS:  # not normalized string comparison
                    video.category = 1  # What does the numbers mean?
                    video.location.total_theft += 1
                else:
                    video.category = 0
                video.save()  # save twice => should do in one go
                video.location.save(update_fields=["total_theft"])  # not atomic transactions
                return HttpResponse(json.dumps({"success": "label updated"}), status=200)
            except Exception:
                return HttpResponse(json.dumps({"errors": "error processing"}), status=500)
    else:
        return HttpResponse(json.dumps({"errors": "invalid method"}), status=405)
