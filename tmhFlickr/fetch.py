import flickr_api as f
import json
import os
import urllib.request
from .utils import extract_filename, strip_extension, say, write_to_file
from flickr_api.api import flickr as flickrapi

RETRIES=10
PER_PAGE=400
NSID_BLACKLIST=['11537427@N04', '9508724@N04', '14928484@N06', '27382352@N03', '38682884@N08',
        '48458761@N00', '129139607@N07', '41618804@N08', '33190334@N06'] # list of NSIDs found to match search but not be of cindy. GENERALISE THIS
EXTRAS=['description, license, date_upload, date_taken, owner_name, icon_server, original_format, '
        'last_update, geo, tags, machine_tags, o_dims, media, path_alias, url_t, url_l, url_o']

def set_auth(key, secret, user_creds_file):
  f.set_keys(api_key = key, api_secret = secret)
  f.set_auth_handler(user_creds_file)

def enable_cache(enable):
  if enable:
    f.enable_cache()
  else:
    f.disable_cache()

def get_photofile(photo):
  for i in range(RETRIES):
    try:
      photofile = photo.getPhotoFile()
    except Exception as e:
      log('{}: Exception {} retrying'.format(extract_filename(meta_file), e))
      continue
    else:
      break

  if "Site MP4" in photo.sizes.keys():
    url = photo.sizes['Site MP4']['source']
    opener = urllib.request.build_opener(urllib.request.HTTPHandler)
    Request = urllib.request.Request
    request = Request(url, method='HEAD')
    response = opener.open(request)
    photofile = response.headers.get_filename()
  elif "Original" in photo.sizes.keys():
    photofile = photo.sizes['Original']['source']
  return photofile

def get_photo_meta(photo):
  exif = []
  exif = json.loads(flickrapi.photos.getExif(photo_id=photo.id, format="json", nojsoncallback=1))
  if exif['stat'] == 'fail':
    exif = []

  data = {
    'info': json.loads(flickrapi.photos.getInfo(photo_id=photo.id, format="json", nojsoncallback=1)),
    'exif': exif,
    'comments': json.loads(flickrapi.photos.comments.getList(photo_id=photo.id, format="json", nojsoncallback=1)),
    'contexts': json.loads(flickrapi.photos.getAllContexts(photo_id=photo.id, format="json", nojsoncallback=1)),
    'people': json.loads(flickrapi.photos.people.getList(photo_id=photo.id, format="json", nojsoncallback=1)),
  }
  return data

def get_with_pagination(func, limit=None, **kwargs):
  data = []
  current_page = 1
  total_pages = 2

  while current_page <= total_pages:
    if current_page > 1:
      log('Requesting page {} of {}'.format(current_page, total_pages))

    res = func(
      **kwargs,
      per_page = PER_PAGE,
      page = current_page
    )
    current_page += 1
    total_pages = res.info.pages
    data = data + res.data

    if limit is not None and current_page >= limit:
      break
  return data

def verified_save_path(photo, save_path):
  save_path = os.path.join(save_path, photo.taken.split()[0])
  if not os.path.exists(save_path):
    os.makedirs(save_path)
  return save_path

def filename(photo):
  return extract_filename(get_photofile(photo))

def fetch_by_id(id, save_path):
  photo = f.Photo(id=id)
  return fetch(photo, save_path)

def fetch_photolist(photolist, save_path, limit=None):
  processed = 0
  for photo in photolist:
    if processed == limit:
      break
    processed += 1

    for i in range(RETRIES):
      try:
        print('{}/{}: {}'.format(processed, len(photolist), filename(photo)))
        fetch(photo, save_path, 1)
      except Exception as e:
        log('Exception {} retrying'.format(e))
        continue
      else:
        break

def fetch(photo, save_path, retries=RETRIES):
  if photo.owner.id in NSID_BLACKLIST:
    log("owned by blacklisted NSID, skipping")
    return False

  for i in range(retries):
    try:
      media_file = os.path.join(verified_save_path(photo, save_path), filename(photo))
      meta_file = os.path.join(verified_save_path(photo, save_path), "{}.json".format(strip_extension(filename(photo))))

      if not os.path.isfile(media_file):
        log('{}: fetching photo'.format(extract_filename(media_file)))
        fetch_photo(photo, media_file)

      if not os.path.isfile(meta_file):
        log('{}: fetching meta'.format(extract_filename(meta_file)))
        fetch_meta(photo, meta_file)
    except Exception as e:
      log('Exception {} retrying'.format(e))
      continue
    else:
      break

  return True

def fetch_meta(photo, meta_file):
  meta = get_photo_meta(photo)
  write_to_file(meta, meta_file)

def fetch_photo(photo, media_file):
  if "Site MP4" in photo.sizes.keys():
    # we have video so we need to do some direct fetching
    url = photo.sizes['Site MP4']['source']
    temp_filename, headers = urllib.request.urlretrieve(url)
    os.rename(temp_filename, media_file)
  elif "Original" in photo.sizes.keys():
    photo.save(strip_extension(media_file), 'Original')
  else:
    size = photo._getLargestSizeLabel()
    photo.sizes[size]['source'] = remove_zzs(photo.sizes[size]['source'])
    photo.save(strip_extension(filename))

def log(message):
  say(message)
