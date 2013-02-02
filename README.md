OnlienStoreTextTools:
======================
Online Store text tools are utility/automation script to generate/update necessary files 
for Unity Online Store from Google Docs.

Required software:
-------------------------------
* python (>2.7)
* gdata-2.0.17 : http://code.google.com/p/gdata-python-client/

Installing Google Data API python client
---------------------------------------
* Download gdata-2.0.17 from google code : http://code.google.com/p/gdata-python-client/downloads/detail?name=gdata-2.0.17.tar.gz
* Extract gdata-2.0.17.tar.gz
* Open Terminal, and go gdata-2.0.17 directory
* Read INSTALL.txt
* (for mac) Type: $> sudo python setup.py install
* or Type: $> python setup.py install --home=[path/to/your/home]

then, goto OnlineStoreTextTools directory, type
* $> storelicense.py

and if you get help text instead of errors, you are ready to use it.


Example Command:
------------------
Downloading i17n store Google Docs settings as JSON:
*  $> ./storelicense.py --user [your@google.acount] --password [your.password] --key [your.doc.key] 
  
Uploading JSON file and modify store Google Docs settings, leaving removed items unchanged:
*  $> ./storelicense.py --user [your@google.acount] --password [your.password] --key [your.doc.key] --upload ./myfile.json

Uploading JSON file and modify store Google Docs settings, also removing items that doesn't exist in given JSON:
*  $> ./storelicense.py --user [your@google.acount] --password [your.password] --key [your.doc.key] --upload ./myfile.json --fullsync

