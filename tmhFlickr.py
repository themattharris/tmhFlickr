# https://python3-exiv2.readthedocs.io/en/latest/tutorial.html#reading-and-writing-xmp-tags

# TODO
# add group fetching
# move save path to a project location e.g. /Download/flickr/<searchterm>
# add a meta reprocessor function (uses the saves json)

import flickr_keys
import json
import flickr_api as f
import os
import pyexiv2
import sys
import threading
import urllib.request
from flickr_api.api import flickr
from pprint import pprint as pp
from math import ceil

PER_PAGE=400
EXTRAS=['description, license, date_upload, date_taken, owner_name, icon_server, original_format, '
        'last_update, geo, tags, machine_tags, o_dims, media, path_alias, url_t, url_l, url_o']
ALLOW_SKIPPING=True
THREADS=4

f.set_keys(api_key = flickr_keys.API_KEY, api_secret = flickr_keys.API_SECRET)

def authorize():
  a = f.auth.AuthHandler()
  perms = "read"
  url = a.get_authorization_url(perms)
  say("Go here and then come back: {}".format(url))
  verifier = input('Enter the oauth_verifier value from the webpage shown after you authorized access: ')
  a.set_verifier(verifier)
  f.set_auth_handler(a)
  user = whoami()

  creds_file = "{}_auth.txt".format(user.username)
  a.save(creds_file)
  say("Saved as {}".format(creds_file))

def emit(obj):
  pp(obj)

def emit_dict(obj):
  pp(obj.__dict__)

def say(message):
  print(message)

def say_with_photo(photo, message):
  say('{}: {}'.format(extract_filename(photo.getPhotoFile()), message))

def uniq_photolist(photo_list):
  seen = set()
  uniq = []
  for p in photo_list:
    if p.id not in seen:
      uniq.append(p)
      seen.add(p.id)
  return uniq

def extract_filename(url):
  return remove_zzs(os.path.basename(url))

def remove_zzs(str):
  suffix = '?zz=1'
  # this suffix gets put into the filename so remove it
  if str.endswith(suffix):
    str = str[:-(len(suffix))]
  return str

def filename_no_ext(filename):
  return os.path.splitext(filename)[0]

def enable_cache(enable):
  if enable:
    f.enable_cache()
  else:
    f.disable_cache()

def get_with_pagination(func, limit=None, **kwargs):
  data = []
  current_page = 1
  total_pages = 2

  while current_page <= total_pages:
    if current_page > 1:
      say('Requesting page {} of {}'.format(current_page, total_pages))

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

def whoami():
  return f.test.login()

def get_user(username):
  return f.Person.findByUserName(username)

def get_photo_by_id(id):
  p = f.Photo(id=id)
  p.getInfo()
  return p

# Returns a list of groups to which you can add photos.
def get_groups():
  return get_with_pagination(f.Group.getGroups)

# Return photos from the given user's photostream. Only photos visible to the calling user will be returned. This method must be authenticated;
def get_user_photos(user, limit=5):
  return get_with_pagination(user.getPhotos, extras=EXTRAS)

def get_photo_meta(photo):
  exif = []
  exif = json.loads(flickr.photos.getExif(photo_id=photo.id, format="json", nojsoncallback=1))
  if exif['stat'] == 'fail':
    exif = []

  data = {
    'info': json.loads(flickr.photos.getInfo(photo_id=photo.id, format="json", nojsoncallback=1)),
    'exif': exif,
    'comments': json.loads(flickr.photos.comments.getList(photo_id=photo.id, format="json", nojsoncallback=1)),
    'contexts': json.loads(flickr.photos.getAllContexts(photo_id=photo.id, format="json", nojsoncallback=1)),
    'people': json.loads(flickr.photos.people.getList(photo_id=photo.id, format="json", nojsoncallback=1)),
  }
  return data

# Returns a list of pool photos for a given group, based on the permissions of the group and the user logged in (if any).
def get_group_photos(group):
  return get_with_pagination(group.getPhotos, extras=EXTRAS)

def get_photosof(user, tags=None, text=None):
  say('Requesting photosOf {}'.format(user.username))
  data = get_with_pagination(user.getPhotosOf, extras=EXTRAS)
  if tags is not None:
    say('Requesting photos with tags: {}'.format(tags))
    data = data + get_with_pagination(f.Photo.search, extras=EXTRAS, tags=tags)

  if text is not None:
    if not isinstance(text, list):
      text = [text]
    for t in text:
      say('Requesting photos using text search of: {}'.format(t))
      data = data + get_with_pagination(f.Photo.search, extras=EXTRAS, text=t)

  return uniq_photolist(data)

def get_photofile(photo):
  photofile = photo.getPhotoFile()
  if "Original" in photo.sizes.keys():
    photofile = photo.sizes['Original']['source']
  return photofile

# iterate over the photos
# download them, 
# store them in an output directory under the yyyy-mm-dd they were taken
# set the meta from the meta
# store the meta in a json blob with the same name
def process_photolist(photo_list):
  from threading import Thread
  from itertools import zip_longest

  size = ceil(len(photo_list) / THREADS)
  bags = zip(*(iter(photo_list),) * size)
  say("Processing across {} threads with bag size {}".format(THREADS, size))
  for bag in bags:
    t = Thread(target=process_photolist_for_real, args=(bag,))
    try:
      t.start()
    except Exception as e:
      print('Exception in thread: {}'.format(e))
      pass

def process_photolist_for_real(photo_list, limit=None):
  processed = 0
  for photo in photo_list:
    if processed == limit:
      break
    processed += 1

    message = 'Processing ({}/{})'.format(processed, len(photo_list))
    process_photo(photo, message)
  say('(T{}): DONE {}/{}'.format(threading.get_ident(), processed, len(photo_list)))

def process_photo(photo, progress_message=None):
  filename = extract_filename(get_photofile(photo))
  save_path = os.path.join('/Users', 'themattharris', 'Downloads', 'flickr', 'cindyli', photo.taken.split()[0])

  if "Site MP4" in photo.sizes.keys():
    filename = "{}.mp4".format(photo.id)

  if not os.path.exists(save_path):
    os.makedirs(save_path)

  # don't do anything if the file already exists
  full_path = os.path.join(save_path, filename)
  if os.path.isfile(full_path) and ALLOW_SKIPPING:
    # say_with_photo(photo, "already retrieved. skipping.")
    return

  say_with_photo(photo, progress_message)

  if "Site MP4" in photo.sizes.keys():
    # we have video so we need to do some direct fetching
    url = photo.sizes['Site MP4']['source']
    urllib.request.urlretrieve(url, os.path.join(save_path, filename))
  elif "Original" in photo.sizes.keys():
    photo.save(os.path.join(save_path, filename_no_ext(filename)), 'Original')
  else:
    size = photo._getLargestSizeLabel()
    photo.sizes[size]['source'] = remove_zzs(photo.sizes[size]['source'])
    photo.save(os.path.join(save_path, filename_no_ext(filename)))

  # save the meta to json for future use
  meta = get_photo_meta(photo)
  serialize_to_file(photo, meta, save_path, filename_no_ext(filename))
  # update the image meta

  if filename.endswith('gif') or filename.endswith('mp4'):
    # TODO: we can't save meta into these filetypes
    return

  try:
    update_photometa(photo, meta, save_path, filename)
  except Exception as e:
    print('EXCEPTION: {} while processing. {}. Deleting files.'.format(filename, str(e)))
    if os.path.isfile(full_path):
      os.remove(full_path)

    meta_file = os.path.join(save_path, "{}.json".format(filename))
    if os.path.isfile(meta_file):
      os.remove(meta_file)
    pass

def serialize_to_file(photo, meta, save_path, filename):
  save_path = os.path.join(save_path, "{}.json".format(filename))
  say_with_photo(photo, 'saving meta to {}'.format(save_path))
  with open(save_path, 'w') as outfile:
    json.dump(meta, outfile)

def update_photometa(photo, meta, save_path, filename):
  say_with_photo(photo, 'Updating meta')
  # from inspection - looks like tags are already in there, as is geo
  # need to set description and title though
  metadata = pyexiv2.ImageMetadata(os.path.join(save_path, filename))
  metadata.read()

  if not 'Exif.Image.DateTime' in metadata.exif_keys:
    # always set this if it wasn't found
    metadata['Exif.Image.DateTime'] = photo.taken

  if len(meta['exif']) > 0:
    say_with_photo(photo, "Coping exif from flickr")
    metadata = copy_meta_from_flickr(photo, metadata, meta)
            
  metadata['Xmp.dc.title'] = meta['info']['photo']['title']['_content']
    
  description = "{}\n{}".format(meta['info']['photo']['title']['_content'], meta['info']['photo']['description']['_content']).strip()
  metadata['Exif.Image.ImageDescription'] = description
  metadata['Xmp.dc.description'] = description
  
  metadata['Exif.Image.ImageID'] = meta['info']['photo']['urls']['url'][0]['_content']
  metadata['Xmp.dc.source'] = meta['info']['photo']['urls']['url'][0]['_content']
  
  metadata['Exif.Image.Artist'] = meta['info']['photo']['owner']['username']
  metadata['Xmp.dc.creator'] = [meta['info']['photo']['owner']['username']]

  subjects = []
  subjects.append("owner:{}".format(meta['info']['photo']['owner']['username']))
  
  for tag in meta['info']['photo']['tags']['tag']:
    subjects.append(tag['raw'])

  for person in meta['people']['people']['person']:
    subjects.append("person:{}".format(person['username']))

  for context in meta['contexts']:
    for c in meta['contexts'][context]:
      if context == 'stat':
        continue
      subjects.append("{}:{}".format(context, c['title']))

  metadata['Xmp.dc.subject'] = subjects
  metadata['Iptc.Application2.Keywords'] = subjects
  say_with_photo(photo, 'Writing meta to photo')
  metadata.write()

# sometimes we don't get the original image (permissions), but flickr still lets us see
# the exif from the api. re-insert the exif into the image we got back.
def copy_meta_from_flickr(photo, metadata, meta):
  for exif in meta['exif']['photo']['exif']:
    tagspace = ''
    if exif['tagspace'] == 'ExifIFD':
      tagspace = 'Exif.Photo'
    elif exif['tagspace'] == 'IFD0':
      tagspace = 'Exif.Image'
    elif exif['tagspace'] == 'JFIF':
      tagspace = 'Exif.Image'
    elif exif['tagspace'] == 'GPS':
      tagspace = 'Exif.GPSInfo'
    # else:
    #   say_with_photo(photo, 'ERROR: Unknown tagspace: {}'.format(exif['tagspace']))

    key = "{}.{}".format(tagspace, exif['tag'])
    try:
      if key in metadata.exif_keys:
        continue

      value = exif['raw']['_content']
      if key == 'Exif.GPSInfo.GPSAltitudeRef':
        if value.startswith("Above"):
          value = 0
        else:
          value = 1

      metadata[key] = value
      say_with_photo(photo, "Set {} to {}".format(key, value))
    except KeyError as e:
      pass
    except pyexiv2.exif.ExifValueError as e:
      # say("Couldn't set value of {} to {}".format(key, exif['raw']['_content']))
      pass
  return metadata

def inspect_meta(filename):
  metadata = pyexiv2.ImageMetadata(filename)
  metadata.read()
  keys = metadata.xmp_keys + metadata.exif_keys + metadata.iptc_keys
  for key in keys:
    say('{}: {}'.format(key, metadata[key].raw_value))

if len(sys.argv) > 1 and sys.argv[1] == 'fetch':
  f.set_auth_handler(sys.argv[2])
  say('Authenticated as {}'.format(whoami().username))
  cindy = get_user('cindyli')
  photo_list = get_photosof(cindy, 'cindyli,"cindy li",cindylidesign', ['cindy li', 'cindyli'])
  say('Got {} Photos'.format(len(photo_list)))
  process_photolist(photo_list)
elif len(sys.argv) > 1 and sys.argv[1] == 'auth':
  authorize()
elif len(sys.argv) > 1 and sys.argv[1] == 'inspect':
  inspect_meta(sys.argv[2])


# www.flickr.com/photo.gne?id=2333079071

# in python3 to use this file do
# exec(open("tmhFlickr.py").read())
# f.set_auth_handler("cindyli_auth.txt")
# video: 8933537698
# pic: 8621468460
# photo = get_photo_by_id(id)

# matt nsid: 20071329@N00
# cindy nsid: 43082001@N00

# example use
# python3 tmhFlickr.py inspect /Users/themattharris/Downloads/flickr/2017-02-25/31937834368_83d168a05c_o.jpg
# python3 tmhFlickr.py auth
# python3 tmhFlickr.py fetch cindyli_auth.txt