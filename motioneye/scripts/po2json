#!/usr/bin/env node

/*
  po2json wrapper for gettext.js
  https://github.com/mikeedwards/po2json

  Dump a .po file in a json like this one:

  {
    "": {
        "language": "en",
        "plural-forms": "nplurals=2; plural=(n!=1);"
    },
    "simple key": "It's tranlation",
    "another with %1 parameter": "It's %1 tranlsation",
    "a key with plural": [
        "a plural form",
        "another plural form",
        "could have up to 6 forms with some languages"
    ],
    "a context\u0004a contextualized key": "translation here"
  }

*/

var
  fs = require('fs'),
  po2json = require('po2json'),
  argv = process.argv,
  json = {},
  pretty = '-p' === argv[4];

if (argv.length < 4)
  return console.error("Wrong parameters.\nFormat: po2json.js input.po output.json [OPTIONS]\n-p for pretty");

fs.readFile(argv[2], function (err, buffer) {
  var jsonData = po2json.parse(buffer);

  for (var key in jsonData) {
    // Special headers handling, we do not need everything
    if ('' === key) {
      json[''] = {
        'language': jsonData['']['language'],
        'plural-forms': jsonData['']['plural-forms']
      };

      continue;
    }

    // Do not dump untranslated keys, they already are in the templates!
    if ('' !== jsonData[key][1])
      json[key] = 2 === jsonData[key].length ? jsonData[key][1] : jsonData[key].slice(1);
  }

  fs.writeFile(argv[3], JSON.stringify(json, null, pretty ? 4 : 0), function(err) {
    if (err)
      console.log(err);
    else
      console.log('JSON ' + (pretty ? 'pretty' : 'compactly') + ' saved to ' + argv[3]);
  });
});
