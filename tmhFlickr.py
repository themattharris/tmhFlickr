# https://python3-exiv2.readthedocs.io/en/latest/tutorial.html#reading-and-writing-xmp-tags

# TODO
# add checks for errors- try catch
# (done) add data taken check - some of these are missing them
# (done) move title into description as well
# (done) add in a txt search when getting photosOf (not just PhotosOf and tags)
# (done) fix serialization bug. F object doesn't pickle properly
# (done) save meta to disc
# (done) add "auth" flow helper

import flickr_keys
import json
import flickr_api as f
import os
import pyexiv2
import sys
import threading
from flickr_api.api import flickr
from pprint import pprint as pp
from math import ceil

PER_PAGE=400
EXTRAS=['description, license, date_upload, date_taken, owner_name, icon_server, original_format, '
        'last_update, geo, tags, machine_tags, o_dims, media, path_alias, url_t, url_l, url_o']
THREADS=8

FLICKR_TAG_MAPPINGS={
  # 'JFIF.JFIFVersion': ''
  # 'JFIF.ResolutionUnit': ''
  'JFIF.XResolution': 'Exif.Image.XResolution',
  'JFIF.YResolution': 'Exif.Image.YResolution',
  'IFD0.Make': 'Exif.Image.Make',
  'IFD0.Model': 'Exif.Image.Model',
  'IFD0.Orientation': 'Exif.Image.Orientation',
  'IFD0.ResolutionUnit': 'Exif.Image.ResolutionUnit',
  'IFD0.ModifyDate': 'Exif.Image.DateTime',
  'ExifIFD.ExposureTime': 'Exif.Photo.ExposureTime',
  'ExifIFD.FNumber': 'Exif.Photo.FNumber',
  'ExifIFD.ExifVersion': 'Exif.Photo.ExifVersion',
  'ExifIFD.DateTimeOriginal': 'Exif.Photo.DateTimeOriginal',
  'ExifIFD.CreateDate': 'Exif.Photo.DateTimeDigitized',
  'ExifIFD.CompressedBitsPerPixel': 'Exif.Photo.CompressedBitsPerPixel',
  'ExifIFD.ExposureCompensation': '',
  'ExifIFD.MaxApertureValue': 'Exif.Photo.MaxApertureValue',
  'ExifIFD.MeteringMode': 'Exif.Photo.MeteringMode',
  'ExifIFD.Flash': 'Exif.Photo.Flash',
  'ExifIFD.FocalLength': 'Exif.Photo.FocalLength',
  'ExifIFD.FlashpixVersion': 'Exif.Photo.FlashpixVersion',
  'ExifIFD.ColorSpace': 'Exif.Photo.ColorSpace',
  'ExifIFD.FocalPlaneXResolution': 'Exif.Photo.FocalPlaneXResolution',
  'ExifIFD.FocalPlaneYResolution': 'Exif.Photo.FocalPlaneYResolution',
  'ExifIFD.FocalPlaneResolutionUnit': 'Exif.Photo.FocalPlaneResolutionUnit',
  'ExifIFD.SensingMethod': 'Exif.Photo.SensingMethod',
  'ExifIFD.CustomRendered': 'Exif.Photo.CustomRendered',
  'ExifIFD.ExposureMode': 'Exif.Photo.ExposureMode',
  'ExifIFD.WhiteBalance': 'Exif.Photo.WhiteBalance',
  'ExifIFD.DigitalZoomRatio': 'Exif.Photo.DigitalZoomRatio',
  'ExifIFD.SceneCaptureType': 'Exif.Photo.SceneCaptureType',
}

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
  say('{}: {}'.format(extract_filename(photo.url), message))

def uniq_photolist(photo_list):
  seen = set()
  uniq = []
  for p in photo_list:
    if p.id not in seen:
      uniq.append(p)
      seen.add(p.id)
  return uniq

def extract_filename(url):
  return os.path.splitext(os.path.basename(url))[0]

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
    t.start()

def process_photolist_for_real(photo_list, limit=None):
  processed = 0
  for photo in photo_list:
    if processed == limit:
      break
    processed += 1

    filename = extract_filename(photo.getPhotoFile())
    say('(T{}): Processing {} ({}/{})'.format(threading.get_ident(), filename, processed, len(photo_list)))
    meta = get_photo_meta(photo)

    save_path = os.path.join('/Users', 'themattharris', 'Downloads', 'flickr', photo.taken.split()[0])

    if not os.path.exists(save_path):
      os.makedirs(save_path)

    # don't do anything if the file already exists
    full_path = os.path.join(save_path, "{}.jpg".format(filename))
    if os.path.isfile(full_path):
      say_with_photo(photo, "already retrieved. skipping.")
      continue
    
    # if no size_label is specified the largest available is retrieved
    photo.save(os.path.join(save_path, filename))
    # save the meta to json for future use
    serialize_to_file(photo, meta, save_path, filename)
    # update the image meta
    update_photometa(photo, meta, save_path, filename)

def serialize_to_file(photo, meta, save_path, filename):
  save_path = os.path.join(save_path, "{}.json".format(filename))
  say_with_photo(photo, 'saving meta to {}'.format(save_path))
  with open(save_path, 'w') as outfile:
    json.dump(meta, outfile)

def update_photometa(photo, meta, save_path, filename):
  say_with_photo(photo, 'Updating meta')
  jpgfilename = '{}.jpg'.format(os.path.join(save_path, filename))
  # from inspection - looks like tags are already in there, as is geo
  # need to set description and title though
  metadata = pyexiv2.ImageMetadata(jpgfilename)
  metadata.read()

  if not 'Exif.Image.DateTime' in metadata.exif_keys and len(meta['exif'] > 0):
    say_with_photo(photo, "No exif found trying to copy from flickr")
    metadata = copy_meta_from_flickr(metadata, meta)
  else:
    say_with_photo(photo, "No exif found and none retrieved from flickr. setting datetaken from 'taken'")
    # we have to have the created data so use flickrs datestamp for taken
    metadata['Exif.Image.DateTime'] = photo.taken
            
  metadata['Xmp.dc.title'] = meta['info']['title']
    
  description = "{}\n{}".format(meta['info']['title'], meta['info']['description'])
  metadata['Exif.Image.ImageDescription'] = description
  metadata['Xmp.dc.description'] = description
  
  metadata['Exif.Image.ImageID'] = meta['info']['urls']['url'][0]['text']
  metadata['Xmp.dc.source'] = meta['info']['urls']['url'][0]['text']
  
  metadata['Exif.Image.Artist'] = meta['info']['owner'].username
  metadata['Xmp.dc.creator'] = [meta['info']['owner'].username]

  subjects = []
  subjects.append("owner:{}".format(meta['info']['owner'].username))
  
  # if 'Iptc.Application2.Keywords' in metadata.iptc_keys:
  #   subjects = metadata['Iptc.Application2.Keywords'].value
  for tag in meta['info']['tags']:
    subjects.append(tag.text)

  for person in meta['people']:
    subjects.append("person:{}".format(person.username))

  for contexts in meta['contexts']:
    for context_subtype in contexts:
      subjects.append("context:{}".format(context_subtype.title))

  metadata['Xmp.dc.subject'] = subjects
  metadata['Iptc.Application2.Keywords'] = subjects
  metadata.write()

# sometimes we don't get the original image (permissions), but flickr still lets us see
# the exif from the api. re-insert the exif into the image we got back.
def copy_meta_from_flickr(metadata, meta):
  for exif in meta['exif']:
    key = "{}.{}".format(meta['exif']['tagspace'], meta['exif']['tag'])
    metadata[FLICKR_TAG_MAPPINGS[key]] = exif.raw
  return metadata

def inspect_meta(filename):
  metadata = pyexiv2.ImageMetadata(filename)
  metadata.read()
  keys = metadata.xmp_keys + metadata.exif_keys + metadata.iptc_keys
  for key in keys:
    print('{}: {}'.format(key, metadata[key].raw_value))

if len(sys.argv) > 1 and sys.argv[1] == 'fetch':
  f.set_auth_handler(sys.argv[2])
  cindy = get_user('cindyli')
  photo_list = get_photosof(cindy, 'cindyli,"cindy li",cindylidesign', ['cindy li', 'cindyli'])
  print('Got {} Photos'.format(len(photo_list)))
  process_photolist(photo_list)
elif len(sys.argv) > 1 and sys.argv[1] == 'auth':
  authorize()
elif len(sys.argv) > 1 and sys.argv[1] == 'inspect':
  inspect_meta(sys.argv[2])

# f.set_auth_handler("cindyli_auth.txt")
# photo = get_photo_by_id(112121201)

# in python3 to use this file do
# exec(open("ripr.py").read())

# matt nsid: 20071329@N00
# cindy nsid: 43082001@N00

# example use
# python3 tmhFlickr.py inspect /Users/themattharris/Downloads/flickr/2017-02-25/31937834368_83d168a05c_o.jpg
# python3 tmhFlickr.py auth
# python3 tmhFlickr.py fetch cindyli_auth.txt