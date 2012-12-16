#!/usr/bin/python
#
# Copyright (C) 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


__author__ = 'hiroki@unity3d.com(Hiroki Omae)'


try:
	from xml.etree import ElementTree
except ImportError:
	from elementtree import ElementTree

import gdata.spreadsheet.service
import gdata.service
import atom.service
import gdata.spreadsheet
import atom
import getopt
import sys
import string
import argparse
import json
import fileinput
import re

g_charcode = 'utf-8'


# features = dictionary { title_en : obj }
# value of features
#   obj.title 		= dictionary {"en":"title text of en", "ja":"title text of ja", ...}
#   obj.description = dictionary {"en":"description text of en", "ja":"description text of ja", ...}
#   obj.category 	= "category text"
#	obj.platform	= dictionary {"Unity":False, "Unity Pro":True, ...}
#	obj.notes		= dictionary {"Unity":"note", "Unity Pro":"note", ...}
#
class StoreLicenseInfo:
	# note: the order of knownPlatforms is the order of platform/notes array
	# in exporting format
	knownPlatforms = ['unitypro', 'unity', 'iospro', 'ios',
					  'androidpro', 'android', 'flashpro', 'flash']
	default_locale = 'en'

	def __init__(self):
		self.title = {}
		self.description = {}
		self.category = None
		self.platform = {}
		self.notes = {}

	def showInfo(self):
		print '------------------------'
		print 'title={0}'.format(self.title).encode(g_charcode)
		print 'description={0}'.format(self.description).encode(g_charcode)
		print 'category={0}'.format(self.category).encode(g_charcode)
		print 'platform={0}'.format(self.platform).encode(g_charcode)
		print 'notes={0}'.format(self.notes).encode(g_charcode)

  # {
  #   "title"       : "Physics",
  #   "description" : "Bring your interactions to life with the built-in NVIDIA PhysX&trade; physics engine. <a href='http://unity3d.com/unity/engine/physics'>Read more</a>",
  #   "category"    : "general",
  #   "platform"    : ["check ","check ","check ","check ","check ","check ","check ","check "],
  #   "notes"       : ["&nbsp;","&nbsp;","&nbsp;","&nbsp;","&nbsp;","&nbsp;","&nbsp;","&nbsp;"]
  # },

	def JSONExpression(self):
		uTitleDesc = self._JSONExpression_localizedTitleDescription()
		uPlatform = self._JSONExpression_platform()
		uNotes = self._JSONExpression_notes()
		out_string = u'''{{
			{0},
			"category"		:	"{1}",
			"platform"		:	[{2}],
			"notes"			:	[{3}]
		}}'''  # {{ and }} is escape for {} not being recognized as formatter
		return out_string.format(uTitleDesc, self.category, uPlatform, uNotes).encode(g_charcode)

	def _JSONExpression_localizedTitleDescription(self):

		out_string = u''
		keys = self.title.keys()
		for key in keys:
			if key is self.default_locale:
				out_string += u'"title" : "{0}",'.format(self.title[key])
				out_string += u'"description" : "{0}"'.format(
					self.description[key])
			else:
				out_string += u'"title_{0}" : "{1}",'.format(
					key, self.title[key])
				out_string += u'"description_{0}" : "{1}"'.format(
					key, self.description[key])
			if key is not keys[-1]:
				out_string += u','
		return out_string

	def _JSONExpression_platform(self):
		out_string = u''
		for key in StoreLicenseInfo.knownPlatforms:
			check = u"check" if self.platform[key] else u""
			out_string += u'"{0}"'.format(check)
			if key is not StoreLicenseInfo.knownPlatforms[-1]:
				out_string += u','
		return out_string

	def _JSONExpression_notes(self):
		out_string = u''
		for key in StoreLicenseInfo.knownPlatforms:
			note = self.notes[key]
			out_string += u'"{0}"'.format(note)
			if key is not StoreLicenseInfo.knownPlatforms[-1]:
				out_string += u','
		return out_string


#
#  Unity Store json file manager
#  All data stored in Google docs (Spreadsheet)
#
class StoreLicenseParser:
	def __init__(self, email, password, doc_key):
		self.gd_client = gdata.spreadsheet.service.SpreadsheetsService()
		self.gd_client.email = email
		self.gd_client.password = password
		self.gd_client.source = 'SpreadSheetToJson'
		self.gd_client.ProgrammaticLogin()
		self.doc_key = doc_key
		self.curr_wksht_id = 'default'
		self.list_feed = None
		self.knownSheets = ['default', 'notes', 'platform']
		self.sheets = {}  # name:id dictionary of each sheets
		self.features = {}  # all values representation
		# login and get all necessary information from spreadsheet on google
		# docs
		self._GetAllWorksheetsIds()

	# Get the list of worksheets
	def _GetAllWorksheetsIds(self):
		feed = self.gd_client.GetWorksheetsFeed(self.doc_key)

		# sheet id looks like this:
		#   https://spreadsheets.google.com/feeds/worksheets/0AqJa9l8Ism8gdE9JeWFxMnhGS1FYZHdQQ01SNDNOTmc/private/full/od5
		# sheet id of file is the last token (i.e:od5)
		for i, entry in enumerate(feed.entry):
			id_parts = entry.id.text.split('/')
			worksheet_id = id_parts[len(id_parts) - 1]
			worksheet_name = entry.title.text
			self.sheets[worksheet_name] = worksheet_id

	#
	# Get all sheets and make intermediate object for exporting/importing
	#
	def _SheetToObject(self):
		self._ParseDefaultSheet()
		self._ParsePlatformSheet()
		self._ParseNotesSheet()

		# if not known sheet, must be for localization:
		for key in self.sheets:
			if key not in self.knownSheets:
				self._ParseLocalizedSheet(key)

	#
	# takes care of 'default' sheet
	#
	def _ParseDefaultSheet(self):
		feed = self.gd_client.GetListFeed(self.doc_key, self.sheets['default'])

		for i, entry in enumerate(feed.entry):
			for key in entry.custom:
				s = unicode(entry.custom[key].text)
				if key == 'title':
					obj.title[StoreLicenseInfo.default_locale] = s
				elif key == 'description':
					obj.description[StoreLicenseInfo.default_locale] = s
				elif key == 'category':
					obj.category = s
		self.features[obj.title[StoreLicenseInfo.default_locale]] = obj

	#
	# takes care of platform checksheet
	#
	def _ParsePlatformSheet(self):
		feed = self.gd_client.GetListFeed(
			self.doc_key, self.sheets['platform'])

		for i, entry in enumerate(feed.entry):
			ref_title = ''
			plaf_dic = {}

			for key in entry.custom:
				s = unicode(entry.custom[key].text.strip())
				if key == 'ref-title':
					ref_title = s
				else:
					plaf_dic[key] = (s == 'check')

			try:
				obj = self.features[ref_title]
				obj.platform = plaf_dic
			except KeyError:
				pass

	#
	# takes care of notes sheet
	#
	def _ParseNotesSheet(self):
		feed = self.gd_client.GetListFeed(self.doc_key, self.sheets['notes'])

		for i, entry in enumerate(feed.entry):
			ref_title = ''
			note_dic = {}

			for key in entry.custom:
				s = unicode(entry.custom[key].text)
				if key == 'ref-title':
					ref_title = s
				else:
					note_dic[key] = s

			try:
				obj = self.features[ref_title]
				obj.notes = note_dic
			except KeyError:
				pass

	#
	# takes care of localization sheet for all locales found
	#
	def _ParseLocalizedSheet(self, lang):
		feed = self.gd_client.GetListFeed(self.doc_key, self.sheets[lang])

		for i, entry in enumerate(feed.entry):
			ref_title = ''
			localized_title = ''
			localized_desc = ''

			for key in entry.custom:
				s = unicode(entry.custom[key].text)
				if key == 'ref-title':
					ref_title = s
				elif key == 'title':
					localized_title = s
				elif key == 'description':
					localized_desc = s

			try:
				obj = self.features[ref_title]
				obj.title[lang] = localized_title
				obj.description[lang] = localized_desc
			except KeyError:
				pass

	#
	# prepare internal data structure from google docs contents
	#
	def LoadDocumentFromGoogleDocs(self):
		self._SheetToObject()

	#
	# prepare internal data structure from given json file
	#
	def LoadDocumentFromJSONFile(self, file_path):
		jsonStr = ''
		#with fileinput.input(files=(file_path)) as f:
		f = fileinput.input(files=(file_path))
		for line in f:
			jsonStr += line.strip()
		jsonObj = json.loads(jsonStr)

		pattern_title = re.compile("title_([a-z\-_]+)")
		pattern_desc = re.compile("description_([a-z\-_]+)")

		for feature in jsonObj["features"]:
			obj = StoreLicenseInfo()
			for key in feature:
				if key == 'title':
					obj.title[StoreLicenseInfo.default_locale] = feature[key]
				elif key == 'description':
					obj.description[
						StoreLicenseInfo.default_locale] = feature[key]
				elif key == 'category':
					obj.category = feature[key]
				elif key == 'platform':
					pf_list = feature[key]
					for i in range(len(StoreLicenseInfo.knownPlatforms)):
						obj.platform[StoreLicenseInfo.knownPlatforms[
							i]] = (pf_list[i].strip() == 'check')
				elif key == 'notes':
					nt_list = feature[key]
					for i in range(len(StoreLicenseInfo.knownPlatforms)):
						obj.notes[
							StoreLicenseInfo.knownPlatforms[i]] = nt_list[i]
				else:
					# if none of known keys, try find localized title/desc
					search_localized_title = pattern_title.search(key)
					if search_localized_title:
						locale = search_localized_title.group(0)
						obj.title[locale] = feature[key]
					else:
						search_localized_desc = pattern_desc.search(key)
						if search_localized_desc:
							locale = search_localized_desc.group(0)
							obj.description[locale] = feature[key]

			self.features[feature['title']] = obj

	#
	# print internal structure in json form
	#
	def ExportSheet(self):
		self._PrintInJSON()

	#
	# print internal structure in json form
	#
	def _PrintInJSON(self):
		jsonStr = ''
		jsonStr += '{ "features": [ '
		keys = self.features.keys()
		for key in keys:
			objStr = self.features[key].JSONExpression()
			jsonStr += objStr
			if key is not keys[-1]:
				jsonStr += ','
		jsonStr += ']}'
		jsonObj = json.loads(jsonStr)
		print json.dumps(jsonObj, sort_keys=True, indent=4).encode('utf-8')

	#
	# upload internal structure to google doc
	#
	def UploadSheet(self, isFullSync):
		print "TODO!!"
		self._UpdateDefaultSheet(isFullSync)
		self._UpdatePlatformSheet(isFullSync)
		self._UpdateNotesSheet(isFullSync)
		# TODO: do all locales
		#self._UpdateLocalizedSheet(isFullSync, lang)

	#
	# update sheet from local data: for default sheet
	#
	def _UpdateDefaultSheet(self, isFullSync):
		feed = self.gd_client.GetListFeed(self.doc_key, self.sheets['default'])

		existing_feature_list = []
		for i, entry in enumerate(feed.entry):
			existing_feature_list.append(
				unicode(entry.custom['title'].text))
			strTitle = unicode(entry.custom['title'].text)

		#
		# removing unexisting entries
		if isFullSync:
			removing_item_set = set(existing_feature_list) - set(self.features.keys())
			print "deleting {0}".format(removing_item_set)
			for feature in removing_item_set:
				for i, entry in enumerate(feed.entry):
					if feature is entry.custom['title'].text:
						print 'Removing item:{0}'.format(feature)
						self.gd_client.DeleteRow(entry)

		#
		# modifying existing entries with local data
		for i, entry in enumerate(feed.entry):
			strTitle = unicode(entry.custom['title'].text)
			try:
				obj = self.features[strTitle]
				newData = {}
				newData['title'] 		= obj.title[StoreLicenseInfo.default_locale]
				newData['description'] 	= obj.description[StoreLicenseInfo.default_locale]
				newData['category'] 	= obj.category
				isDirty = ( entry.custom['title'].text != newData['title'] )
				isDirty |= ( entry.custom['description'].text != newData['description'] )
				isDirty |= ( entry.custom['category'].text != newData['category'] )
				if isDirty:
					print "Updating:{0}".format(strTitle)
					self.gd_client.UpdateRow(entry,newData)
			except KeyError:
				print 'Object for "{0}" not found.'.format(strTitle)
				pass  # don't worry if strTitle is not found

		#
		# adding new entries only exist in local data
		new_item_set = set(self.features.keys()) - set(existing_feature_list)
		for feature in new_item_set:
			try:
				obj = self.features[feature]
				newData = {}
				newData['title'] 		= obj.title[StoreLicenseInfo.default_locale]
				newData['description'] 	= obj.description[StoreLicenseInfo.default_locale]
				newData['category'] 	= obj.category
				entry = self.gd_client.InsertRow(newData, self.doc_key, self.sheets['default'])
				if not isinstance(entry, gdata.spreadsheet.SpreadsheetsList):
					print 'Error: Failed to add {0}'.format(feature)
			except KeyError:
				print 'FATAL: Object for "{0}" not found.'.format(feature)
				pass  # don't worry if strTitle is not found


	#
	# update sheet from local data: for platform
	#
	def _UpdatePlatformSheet(self, isFullSync):
		feed = self.gd_client.GetListFeed(
			self.doc_key, self.sheets['platform'])
		print "TODO!"

		# for i, entry in enumerate(feed.entry):
		# 	ref_title = ''
		# 	plaf_dic = {}

		# 	if isinstance(feed, gdata.spreadsheet.SpreadsheetsListFeed):
		# 		for key in entry.custom:
		# 			s = unicode(entry.custom[key].text.strip())
		# 			if key == 'ref-title':
		# 				ref_title = s
		# 			else :
		# 				plaf_dic[key] = ( s == 'check' )

		# 	try:
		# 		obj = self.features[ ref_title ]
		# 		obj.platform = plaf_dic
		# 	except KeyError:
		# 		print "key '{0}' not found:".format(ref_title)

	#
	# update sheet from local data: for notes
	#
	def _UpdateNotesSheet(self, isFullSync):
		feed = self.gd_client.GetListFeed(self.doc_key, self.sheets['notes'])
		print "TODO!"

		# for i, entry in enumerate(feed.entry):
		# 	ref_title = ''
		# 	note_dic = {}

		# 	if isinstance(feed, gdata.spreadsheet.SpreadsheetsListFeed):
		# 		for key in entry.custom:
		# 			s = unicode(entry.custom[key].text)
		# 			if key == 'ref-title':
		# 				ref_title = s
		# 			else :
		# 				note_dic[key] = s

		# 	try:
		# 		obj = self.features[ ref_title ]
		# 		obj.notes = note_dic
		# 	except KeyError:
		# 		print "key '{0}' not found:".format(ref_title)

	#
	# update sheet from local data: for localization
	#
	def _UpdateLocalizedSheet(self, isFullSync, lang):
		feed = self.gd_client.GetListFeed(self.doc_key, self.sheets[lang])
		print "TODO!"

		# for i, entry in enumerate(feed.entry):
		# 	ref_title = ''
		# 	localized_title = ''
		# 	localized_desc = ''

		# 	if isinstance(feed, gdata.spreadsheet.SpreadsheetsListFeed):
		# 		for key in entry.custom:
		# 			s = unicode(entry.custom[key].text)
		# 			if key == 'ref-title':
		# 				ref_title = s
		# 			elif key == 'title':
		# 				localized_title = s
		# 			elif key == 'description':
		# 				localized_desc = s

		# 	try:
		# 		obj = self.features[ ref_title ]
		# 		obj.title[lang] = localized_title
		# 		obj.description[lang] = localized_desc
		# 	except KeyError:
		# 		print "key '{0}' not found:".format(ref_title)


	# def _ListInsertAction(self, row_data):
	# 	entry = self.gd_client.InsertRow(self._StringToDictionary(row_data),
	# 		self.doc_key, self.curr_wksht_id)
	# 	if isinstance(entry, gdata.spreadsheet.SpreadsheetsList):
	# 		print 'Inserted!'

	# def _ListUpdateAction(self, index, row_data):
	# 	self.list_feed = self.gd_client.GetListFeed(self.doc_key, self.curr_wksht_id)
	# 	entry = self.gd_client.UpdateRow(
	# 		self.list_feed.entry[string.atoi(index)],
	# 		self._StringToDictionary(row_data))
	# 	if isinstance(entry, gdata.spreadsheet.SpreadsheetsList):
	# 		print 'Updated!'

	# def _ListDeleteAction(self, index):
	# 	self.list_feed = self.gd_client.GetListFeed(self.doc_key, self.curr_wksht_id)
	# 	self.gd_client.DeleteRow(self.list_feed.entry[string.atoi(index)])
	# 	print 'Deleted!'

	# def _StringToDictionary(self, row_data):
	# 	dict = {}
	# 	for param in row_data.split():
	# 		temp = param.split('=')
	# 		dict[temp[0]] = temp[1]
	# 		return dict


def main():

	parser = argparse.ArgumentParser(description='download and format Google spereadsheet to json/properties.')
	parser.add_argument('--user', required=True, help='Google apps user id')
	parser.add_argument(
		'--password', required=True, help='Google apps user password')
	parser.add_argument('--key', required=True, help='key ID of spereadsheet. you can retrieve this from Google Spreadsheet\'s URL.')
	parser.add_argument('--upload', help='instead of downloading from google docs, parse json file and reflect it to google docs.', default='')
	parser.add_argument('--fullsync', action='store_true', help='paired with --upload. --fullsync will remove entries in Spreadsheet that are not in given json.')

	args = parser.parse_args()

	parser = StoreLicenseParser(args.user, args.password, args.key)

	if args.upload is not '':
		parser.LoadDocumentFromJSONFile(args.upload)
		parser.UploadSheet(args.fullsync)
	else:
		parser.LoadDocumentFromGoogleDocs()
		parser.ExportSheet()

if __name__ == '__main__':
	main()
