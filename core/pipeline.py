# users/pipeline.py
import requests
from django.core.files.base import ContentFile
from files.models import Photo  # adjust import path to your Photo model

def save_profile_photo(backend, user, response, *args, **kwargs):
    """
    After the user is created/updated, grab their Google picture URL
    and save it into our Photo model.
    """
    url = None
    if backend.name == 'google-oauth2':
        url = response.get('picture')
    # Apple does not return a photo by default
    if not url:
        return

    resp = requests.get(url)
    if resp.status_code != 200:
        return

    fname = f"{user.username}_google.jpg"
    photo = Photo()
    photo.image.save(fname, ContentFile(resp.content), save=True)
    photo.save()
    user.photo = photo
    user.save()