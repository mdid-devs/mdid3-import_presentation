__author__ = 'hanleybrand'
import os

# I had an odd thing during development where the the command wasn't seeing django in the path
# (it was an ENV error) the commented code below fixes it so you can keep going =)
import sys

# this should be a path to the django on your server that is serving mdid3
# sys.path.append(os.path.expanduser('~/Dev/hacking_gallery/django'))
# # print sys.path
#
# #if the env error happens
# from django.core.management import setup_environ
from rooibos import settings

# setup_environ(settings)

from rooibos.data.models import Record, standardfield, Field, FieldValue, Collection, CollectionItem
from rooibos.presentation.models import Presentation
from rooibos.storage.models import Media, Storage
from rooibos.util import guess_extension

import simplejson
import requests

from StringIO import StringIO
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


try:
    from rooibos.apps.import_presentation import settings_local as setting
except:
    setting = None


class Command(BaseCommand):
    help = 'Attempts to import a Presentation from another mdid3 server\nAvailable commands: server_url \nex: python manage.py presImport http://mdid3.server.edu\nnote: do not add a trailing slash '
    args = 'command'


    def handle(self, *commands, **options):

        mdid_base_url = None

        if not commands:
            print self.help
        else:
            if setting and setting.SERVER:
                mdid_base_url = setting.SERVER
            else:
                for command in commands:
                    # this is the server url entered when the command was typed e.g.:
                    # $> python manage.py import_pres https://mdid3.uni.edu
                    #
                    mdid_base_url = command
                    ## set up variables
        mdid_api = {'auth': mdid_base_url + '/api/login/',
                    'presentations': mdid_base_url + '/api/presentations/currentuser/',
                    'presentation': mdid_base_url + '/api/presentation/', }

        username = raw_input('local admin username -> ')
        prompt_pass = 'enter password for %s (unmasked)-> ' % username
        password = raw_input(prompt_pass)

        if setting and setting.TARGET_USER:
            target_user = User.objects.get(username=setting.TARGET_USER)
        else:
            target_user = chooser(
                raw_input("enter username to own the slideshow being imported. Press Enter for %s > " % username),
                username)

        # these are hard coded, probably not the best practice but I only needed this once
        # if using further, confirm the storage & collection pks are correct before running
        fid = Field.objects.get(label='ID', standard__prefix='aae')
        store = Storage.objects.get(pk=1)
        collection = Collection.objects.get(pk=1)

        def connect():
            print 'connecting via %s' % mdid_api['auth']
            creds = {'username': username, 'password': password}

            try:
                r = requests.post(mdid_api['auth'], data=creds)
            except:
                print 'hmm, %s is not working out, maybe try again...' % mdid_api['auth']
                exit()

            if r.status_code == requests.codes.ok:
                print 'looks ok', r.status_code
                rc = r.cookies
                presentation_select(rc)
            else:
                print 'Huh, some kind of weird error - let\'s try again...\n'
                exit()

        def presentation_select(rc):
            p = requests.get(mdid_api['presentations'], cookies=rc)

            if p.status_code == requests.codes.ok:
                j = simplejson.loads(p.content)
                print('========import presentation for user %s ========================' % target_user)

                for presentation in j['presentations']:
                    print presentation['id'], presentation['title'], presentation['tags']

                print """
                \nenter the id of a presentation above, or type:
                \'all\' to import the entire list  or
                \'quit\' to quit
                """
                which_show = raw_input('enter a slide show id > ')

                if which_show == 'quit':
                    print 'ok, if you want to %s' % which_show
                    exit()
                if which_show == 'all':
                    print 'ok, %s it is!' % which_show
                    pres_list = []
                    for presentation in j['presentations']:
                        pres_list.append(presentation['id'])
                else:
                    pres_list = [which_show]

                presentation_import(pres_list, rc)

        def presentation_import(pres_ids, rc):

            print pres_ids

            for pres_id in pres_ids:

                pres_url = 'http://mdid3.temple.edu/api/presentation/' + str(pres_id) + '/'
                print 'fetching %s' % pres_url

                theShow = requests.get(pres_url, cookies=rc)
                #print theShow.json()

                jp = simplejson.loads(theShow.content)

                concat_description = jp['description']
                presentation = Presentation.objects.create(title=jp['title'],
                                                           owner=target_user,
                                                           description=concat_description)


                # jp['content'] contains every slide
                for order, slide in enumerate(jp['content']):
                    #print order, slide
                    rec_exists = False
                    rec_id = None

                    print 'using storage %s' % store.base

                    for metadata in slide['metadata']:

                        #print 'metadata for slide %s, %s' % (slide['name'], str(metadata))
                        #print metadata

                        if metadata['label'] == 'ID':
                            print 'metadata for slide %s, %s' % (slide['name'], str(metadata))
                            rec_id = metadata['value']
                            print '%s is an ID field' % rec_id
                            #print metadata['value']
                            if Record.by_fieldvalue(fid, rec_id):
                                rec_exists = True
                                print '%s already exists' % rec_id
                            break

                    # when finished checking for ID either add existing record to pres
                    # or create record and then add it

                    if rec_exists:
                        # note that record is the first record in the list that is returned byfieldvalue
                        # which should be checked for accuracy in multiple tests if there's any chance that
                        # there could be multiple records
                        print 'Check the following list list of records for multiple values:'
                        print Record.by_fieldvalue(fid, rec_id)
                        record = Record.by_fieldvalue(fid, rec_id)[0]
                        presentation.items.create(order=order, record=record)
                        presentation.save()
                        print 'adding %s to presentation at position %s' % (rec_id, order)

                    else:
                        print 'creating record for %s' % rec_id
                        print 'metadata:'
                        print slide['metadata']

                        #record = Record.objects.create(name=rec_id, owner=target_user)
                        record = Record.objects.create(owner=target_user)
                        record.save()

                        for metadata in slide['metadata']:
                            try:
                                target = Field.objects.get(label=metadata['label'], standard__prefix='aae')
                                record.fieldvalue_set.create(field=target,
                                                             value=metadata['value'],
                                                             label=metadata['label'], )
                            except Exception as e:
                                print e
                                try:
                                    target = Field.objects.filter(label=metadata['label'])
                                    record.fieldvalue_set.create(field=target[0],
                                                                 value=metadata['value'],
                                                                 label=metadata['label'], )
                                    print "Ok, went with %s the first field I could find to go with!" % target[0]
                                except Exception as e_two:
                                    print e_two
                                    print "ok, giving up!"
                                    continue
                                continue

                        try:
                            title = slide['title']
                        except:
                            title = 'Untitled'

                        FieldValue.objects.create(record=record,
                                                  field=standardfield('title'),
                                                  order=0,
                                                  value=title)

                        col_i = CollectionItem.objects.create(collection=collection, record=record)

                        print 'collection item created: %s' % col_i

                        ## file biz

                        # media_req.content contains the image
                        media_url = mdid_base_url + slide['image']
                        print 'media_url: %s' % media_url
                        media_req = requests.get(media_url, cookies=rc)
                        mimetype = media_req.headers['content-type']

                        file = StringIO(media_req.content)

                        if guess_extension(mimetype) == '.jpeg':
                            filename = record.name + '.jpg'
                            extension = 'JPEG'
                        else:
                            filename = os.path.join(record.name + guess_extension(mimetype))
                            extension = os.path.splitext(mimetype)[0]
                        print 'extension %s' % extension

                        file_path = os.path.join(store.base, filename)

                        print 'saving media file for %s to %s' % (record.name, file_path)

                        media = Media.objects.create(record=record,
                                                     #name=os.path.splitext(file.name)[0],
                                                     name=record.name,
                                                     storage=store,
                                                     mimetype=mimetype)
                        media.save_file(filename, file)

                        presentation.items.create(order=order, record=record)
                        presentation.save()



        if mdid_base_url:
            connect()
        else:
            print 'For some reason no server url is entered - try running the program again'
            exit()


def chooser(another_user, me, inception=0):
    # inception is to keep track of recursive calls to chooser
    if another_user != '':
        try:
            usr = User.objects.get(username=another_user)
        except User.DoesNotExist:
            print 'ALERT: User with username %s not found' % another_user
            another_try = raw_input('Try another username? (Press Enter for %s) > ' % me)
            usr = chooser(another_try, me, inception + 1)
    else:
        try:
            usr = User.objects.get(username=me)
        except User.DoesNotExist:
            print 'ALERT: The account on the remote machine used for login  %s not found on local server' % me
            another_try = raw_input('Try another username? (Press Enter for %s) > ' % me)
            usr = chooser(another_try, me, inception + 1)
    if inception == 0:
        print 'Returning %s for user %s' % (usr.id, usr.username)
    return usr