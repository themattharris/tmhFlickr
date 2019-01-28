# https://python3-exiv2.readthedocs.io/en/latest/tutorial.html#reading-and-writing-xmp-tags

# TODO
# IN PROGRESS add a meta reprocessor function (uses the saves json)
# IN PROGRESS add geo to content - if it's not in exif add it -- extracted, now need to use it
# IN PROGRESS for the meta extractors, check for key else return false

from tmhFlickr import fetch, meta, utils
import flickr_keys
import os

def provision():
  a = fetch.f.auth.AuthHandler()
  perms = "read"
  url = a.get_authorization_url(perms)
  print("Go here and then come back: {}".format(url))

  verifier = input('Enter the oauth_verifier value from the webpage shown after you authorized access: ')
  a.set_verifier(verifier)
  f.set_auth_handler(a)
  user = fetch.f.test.login()

  creds_file = "{}_auth.txt".format(user.username)
  a.save(creds_file)
  print("Saved credentials to {}".format(creds_file))

def get_content_of_username(save_root, username):
  cindy = fetch.f.Person.findByUserName('cindyli')
  matt = fetch.f.Person.findByUserName('themattharris')
  owner = fetch.f.Person.findByUserName(username)

  save_path = os.path.join(save_root, username)
  photolist = fetch.get_with_pagination(fetch.f.Photo.search,
    user_id=owner.id,
    extras=fetch.EXTRAS,
    tags='cindyli,themattharris,mharris,cindylidesign,"cindy li","matt harris"')

  photolist = photolist + fetch.get_with_pagination(cindy.getPhotosOf,
    extras=fetch.EXTRAS,
    owner_id=owner.id)
  photolist = photolist + fetch.get_with_pagination(matt.getPhotosOf,
    extras=fetch.EXTRAS,
    owner_id=owner.id)
  fetch.fetch_photolist(photolist, save_path)

def get_content_of_groups(save_root, group_limit=1000, restrict_to_gids=[]):
  grps = fetch.get_with_pagination(fetch.f.Group.getGroups)

  for g in grps:
    if len(restrict_to_gids) > 0:
      if g.id not in gids:
        continue

    if int(g.photos) > group_limit:
      continue

    print("{}: {} ({})".format(g.id, g.name, g.photos))
    photolist = fetch.get_with_pagination(g.getPhotos, extras=fetch.EXTRAS)
    save_path = os.path.join(save_root, g.name)
    fetch.fetch_photolist(photolist, save_path)

def get_photosof(save_root):
  cindy = fetch.f.Person.findByUserName('cindyli')
  matt = fetch.f.Person.findByUserName('themattharris')
  save_path = os.path.join(save_root, 'photos_of')

  photos_of = fetch.get_with_pagination(cindy.getPhotosOf,
    extras=fetch.EXTRAS)
  tagged = fetch.get_with_pagination(fetch.f.Photo.search,
    extras=fetch.EXTRAS,
    tags='cindyli,"cindy li",cindylidesign')
  searched = fetch.get_with_pagination(fetch.f.Photo.search,
    extras=fetch.EXTRAS,
    text=['cindy li', 'cindyli'])
  cindy_list = photos_of + tagged + searched


  photos_of = fetch.get_with_pagination(matt.getPhotosOf,
    extras=fetch.EXTRAS)
  tagged = fetch.get_with_pagination(fetch.f.Photo.search,
    extras=fetch.EXTRAS,
    tags='mattharris,"matt harris",themattharris')
  searched = fetch.get_with_pagination(fetch.f.Photo.search,
    extras=fetch.EXTRAS,
    text=['themattharris'])
  matt_list = photos_of + tagged + searched

  photolist = cindy_list + matt_list
  fetch.fetch_photolist(photolist, save_path)

def get_photosby(save_root, username):
  owner = fetch.f.Person.findByUserName(username)
  photolist = fetch.get_with_pagination(owner.getPhotos, extras=Flickr.EXTRAS)
  save_path = os.path.join(save_root, username)
  fetch.fetch_photolist(photolist, save_path)

save_root = os.path.join('/Users', 'themattharris', 'Downloads', 'flickr')
fetch.set_auth(flickr_keys.API_KEY, flickr_keys.API_SECRET, os.path.join(os.getcwd(), 'cindyli_auth.txt'))

# examples
####
# get_content_of_username(save_root, 'ginader')

####
# gids = ['77894656@N00', '374158@N21', '946925@N23', '73178834@N00', '1482219@N24', '1941306@N20', '2113136@N23', '983887@N22', '42734174@N00', '41354677@N00', '1445512@N23', '1604380@N24', '553336@N21', '1013372@N25', '980507@N20', '683591@N20', '842476@N20', '423467@N23', '47859600@N00', '1716746@N20', '2613738@N23', '1704127@N24', '72657537@N00', '916659@N21']
# get_content_of_groups(save_root, 5000, gids)

####
# get_photosof(save_root)

####
# fetch.fetch_by_id(8933537698, save_root)

####
media_path = os.path.join('/Users', 'themattharris', 'Downloads', 'flickr', 'ginader', '2010-11-07','5170158196_db1dfc35fa_o.json')
# meta.inspect_cached(media_path)
utils.emit(meta.tags_from_cached(meta.read_cached(media_path)))

# www.flickr.com/photo.gne?id=2333079071
# matt nsid: 20071329@N00
# cindy nsid: 43082001@N00