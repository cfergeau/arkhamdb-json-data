#!/usr/bin/env python

import argparse
import json
import jsonschema
import os
import pathlib
import sys
import re

PACK_DIR="pack"
SCHEMA_DIR="schema"
formatting_errors = 0
validation_errors = 0

def check_dir_access(path):
    if not os.path.isdir(path):
        sys.exit("%s is not a valid path" % path)
    elif os.access(path, os.R_OK):
        return
    else:
        sys.exit("%s is not a readable directory")

def check_file_access(path):
    if not os.path.isfile(path):
        return False;
    elif os.access(path, os.R_OK):
        return True
    else:
        return False

def format_json(json_data):
    formatted_data = json.dumps(json_data, ensure_ascii=False, sort_keys=True, indent=4, separators=(',', ': '))
    formatted_data = formatted_data.replace(u"\u2018", "'").replace(u"\u2019", "'")
    formatted_data = formatted_data.replace(u"\u2212", "-").replace(u"\u2013", "-")
    formatted_data = formatted_data.replace("\\r\\n", "\\n").replace(" \\n", "\\n")
    formatted_data = formatted_data.replace("][", "] [")
    for i in range(8, 0, -1):
         formatted_data = re.sub("^" + ("    " * i), "\t" * i, formatted_data, flags=re.MULTILINE)
    formatted_data += "\n"
    return formatted_data

def load_json_file(args, path):
    global formatting_errors
    global validation_errors
    try:
        with open(path, "rb") as data_file:
            bin_data = data_file.read()
        raw_data = bin_data.decode("utf-8")
        json_data = json.loads(raw_data)
    except ValueError as e:
        verbose_print(args, "%s: File is not valid JSON.\n" % path, 0)
        validation_errors += 1
        verbose_print(args, "%s\n" % e.message, 0)
        return None

    formatted_raw_data = format_json(json_data)

    if "<sup>" in formatted_raw_data:
        verbose_print(args, "%s: File contains invalid content (<sup>)\n" % path, 0)
        validation_errors += 1
        return None

    if formatted_raw_data != raw_data:
        ##verbose_print(args, "%s: File is not correctly formatted JSON.\n" % path, 0)
        formatting_errors += 0
        if args.fix_formatting and len(formatted_raw_data) > 0:
            verbose_print(args, "%s: Fixing JSON formatting...\n" % path, 0)
            try:
                with open(path, "wb") as json_file:
                    bin_formatted_data = formatted_raw_data.encode("utf-8")
                    json_file.write(bin_formatted_data)
            except IOError as e:
                verbose_print(args, "%s: Cannot open file to write.\n" % path, 0)
                print(e)
    return json_data

def load_cycles(args):
    verbose_print(args, "Loading cycle index file...\n", 1)
    cycles_path = os.path.join(args.base_path, "cycles.json")
    cycles_data = load_json_file(args, cycles_path)

    return cycles_data

def load_packs(args, cycles_data):
    verbose_print(args, "Loading pack index file...\n", 1)
    packs_path = os.path.join(args.base_path, "packs.json")
    packs_data = load_json_file(args, packs_path)

    for p in packs_data:
        if p["cycle_code"] == "promotional":
            p["cycle_code"] = "promo"
        pack_filename = "{}.json".format(p["code"])
        pack_path = os.path.join(args.pack_path, p["cycle_code"], pack_filename)
        p['player'] = check_file_access(pack_path)
        pack_filename = "{}_encounter.json".format(p["code"])
        pack_path = os.path.join(args.pack_path, p["cycle_code"], pack_filename)
        p['encounter'] = check_file_access(pack_path)

    return packs_data

def load_subtypes(args):
    verbose_print(args, "Loading subtype index file...\n", 1)
    subtypes_path = os.path.join(args.base_path, "subtypes.json")
    subtypes_data = load_json_file(args, subtypes_path)

    return subtypes_data

def load_types(args):
    verbose_print(args, "Loading type index file...\n", 1)
    types_path = os.path.join(args.base_path, "types.json")
    types_data = load_json_file(args, types_path)

    return types_data

def load_sides(args):
    verbose_print(args, "Loading side index file...\n", 1)
    sides_path = os.path.join(args.base_path, "sides.json")
    sides_data = load_json_file(args, sides_path)

    return sides_data

def parse_commandline():
    argparser = argparse.ArgumentParser(description="Validate JSON in the netrunner cards repository.")
    argparser.add_argument("-f", "--fix_formatting", default=False, action="store_true", help="write suggested formatting changes to files")
    argparser.add_argument("-v", "--verbose", default=0, action="count", help="verbose mode")
    argparser.add_argument("-b", "--base_path", default=os.getcwd(), help="root directory of JSON repo (default: current directory)")
    argparser.add_argument("-p", "--pack_path", default=None, help=("pack directory of JSON repo (default: BASE_PATH/%s/)" % PACK_DIR))
    argparser.add_argument("-c", "--schema_path", default=None, help=("schema directory of JSON repo (default: BASE_PATH/%s/" % SCHEMA_DIR))
    argparser.add_argument("-l", "--languages", default=None, help=("comma-separated list of languages to process (default: all languages)"))
    argparser.add_argument("-s", "--hide-completed", action="store_true", help="whether to show stats for fully translated files")
    argparser.add_argument("i18n_files", nargs="*", default=None, help=("list of json files to process (default: all files for the selected languages)"))

    args = argparser.parse_args()

    # Set all the necessary paths and check if they exist
    if args.schema_path is None:
        args.schema_path = os.path.join(args.base_path,SCHEMA_DIR)
    if args.pack_path is None:
        args.pack_path = os.path.join(args.base_path,PACK_DIR)

    if args.languages is not None:
        args.languages = args.languages.split(",")

    check_dir_access(args.base_path)
    check_dir_access(args.schema_path)
    check_dir_access(args.pack_path)

    return args

def get_languages(args):
    languages = args.languages
    if languages is None:
        base_translations_path = os.path.join(args.base_path, "translations")
        languages = os.listdir(base_translations_path)

    return languages

class i18nLocale(object):
    def __init__(self, locale, base_path = "translations"):
        self.name = locale
        self.base_path = base_path

    def resolvePath(self, enPath):
        return os.path.join(self.base_path, self.name, enPath)

class i18nStats(object):
    def __init__(self, locale, en_file_name):
        self.locale = locale
        self.en_file_name = en_file_name
        self.translated = 0
        self.untranslated = {}
        self.missing = {}

    def print(self, args):
        verbose_print(args, "%s: %s\n"%(self.locale.name, self.en_file_name), 0)
        if not args.hide_completed or len(self.untranslated) != 0:
            verbose_print(args, "%s: translated: %d untranslated: %d\n"%(self.locale, self.translated, len(self.untranslated)), 0)
        if len (self.missing) != 0:
            verbose_print(args, "%s: missing from translated file: %s\n"%(self.locale, self.missing), 0)

    def print_short(self, args):
        if self.translated == self.total and args.hide_completed:
            return
        path = self.locale.resolvePath(self.en_file_name)
        verbose_print(args, "%s (%d / %d)\n"%(path, self.translated, self.total), 0)



def get_translatable_strings(args, item, file_path="", warn_if_extra=True):
    translatable_fields = {'flavor', 'name', 'subname', 'customization_text', 'customization_change', 'text', 'traits', 'back_name', 'back_flavor', 'back_text', 'back_traits', 'slot'}
    result = {}

    extra = set(item).difference(translatable_fields, {'code'})
    if warn_if_extra and len(extra) != 0:
        verbose_print(args, "WARN:get_translatable_strings: extra entries in %s: %s\n"%(file_path, extra), 0)

    for field in translatable_fields:
        if field in item:
            result[field] = item[field]

    return result, len(extra) != 0

def check_duplicate_codes(args, file_data, file_path):
    codes = set()
    for c in file_data:
        code = c.get("code")
        if code in codes:
            verbose_print(args, "WARN: duplicate 'code' %s in %s\n"%(code, file_path), 0)
            continue
        codes.add(code)

def check_extra_i18n_codes(args, i18n_dict, en_dict, file_path):
    extra_i18n = i18n_dict.keys() - en_dict.keys()
    if len(extra_i18n) != 0:
        verbose_print(args, "WARN:check_extra_i18n_codes: extra entries in %s: %s\n"%(file_path, extra_i18n), 0)

def load_translatable_dict(args, file_path, warn_if_extra=False):
    if check_file_access(file_path):
        file_data = load_json_file(args, file_path)
    else:
        verbose_print(args, "WARN: could not load %s\n"%file_path, 1)
        return {}, 0

    check_duplicate_codes(args, file_data, file_path)

    translatables = {}
    total = 0
    found_extra = False
    for c in file_data:
        code = c.get("code")
        if code in translatables:
            verbose_print(args, "WARN: file already has an entry for %s\n"%code, 0)
            continue

        translatable, extra = get_translatable_strings(args, c, file_path, warn_if_extra)
        if extra:
            found_extra = True
        #verbose_print(args, "%s: len(translatable)=%d\n"%(en_file_path, len(translatable)), 0)
        if len(translatable) > 0:
            translatables[c.get("code")] = translatable

        total += len(translatable)
        #verbose_print(args, "got code %s\n"% c.get("code"), 0)

    if found_extra and warn_if_extra:
        verbose_print(args, "json without extra entries:\n%s\n"%format_json(flatten_i18n_dict(translatables)), 1)

    return translatables, total

def should_ignore(ignore_dict, code, field, value):
    if ignore_dict is None:
        return False

    if not code in ignore_dict:
        return False

    if not field in ignore_dict[code]:
        return False

    if ignore_dict[code][field] == value:
        return True

    return False

def flatten_i18n_dict(i18n_dict):
    for key, value in i18n_dict.items():
        value["code"] = key
    return list(i18n_dict.values())

def compare_translations(args, locale, en_file_path):
    en_dict = {}
    total = 0
    en_dict, total = load_translatable_dict(args, en_file_path)

    if total == 0:
        verbose_print(args, "%s: no translatable strings in %s\n"%(locale.name, en_file_path), 1)

    stats = i18nStats(locale, en_file_path)
    stats.total = total

    i18n_file_path = locale.resolvePath(en_file_path)
    i18n_dict, total = load_translatable_dict(args, i18n_file_path, True)

    check_extra_i18n_codes(args, i18n_dict, en_dict, i18n_file_path)

    ignore_file_path = i18n_file_path.removesuffix(".json")+".ignore"
    ignore_dict, total = load_translatable_dict(args, ignore_file_path)

    for code, i18n_strings in i18n_dict.items():
        if not code in en_dict:
            verbose_print(args, "%s: unexpected translated entry: %s\n"%(locale.name, code), 0)
            continue

        untranslated = {}
        en_strings = en_dict[code]
        for field, value in en_strings.items():
            if field in i18n_strings:
                if should_ignore(ignore_dict, code, field, i18n_strings[field]):
                    verbose_print(args, "ignoring %s %s %s\n"%(code, field, i18n_strings[field]), 2)
                    stats.translated+=1
                elif value == i18n_strings[field] and value != "":
                    untranslated[field] = value
                else:
                    stats.translated+=1
            else:
                untranslated[field] = value
        if len(untranslated) > 0:
            stats.untranslated[code] = untranslated
            #verbose_print(args, "%s:%s: %s are not translated\n"%(locale_name, code, untranslated), 1)
        #del en_dict[code]

        en_dict.pop(code)

    stats.missing = en_dict
    if len(stats.missing) != 0:
        verbose_print(args, "missing json:\n%s\n"%format_json(flatten_i18n_dict(stats.missing)), 1)

    if len(stats.untranslated) != 0:
        verbose_print(args, "untranslated json:\n%s\n"%format_json(flatten_i18n_dict(stats.untranslated)), 1)

    return stats

def all_files(args):
    # This does not use args.pack_dir because it is an absolute path while this
    # code needs a relative path. Not sure a separate args.pack_dir makes a lot
    # of sense as `translations/*` is not under args.pack_dir and would not be
    # relocated.
    cycle_dirs = os.listdir(PACK_DIR)
    for cycle_dir in cycle_dirs:
        file_names = os.listdir(os.path.join(PACK_DIR, cycle_dir))
        for file_name in file_names:
            if not file_name.endswith(".json"):
                verbose_print(args, "Ignoring non-json file %s\n" % file_name, 1)
                continue

            yield os.path.join(PACK_DIR, cycle_dir, file_name)

    yield 'cycles.json'
    yield 'encounters.json'
    yield 'factions.json'
    yield 'packs.json'
    yield 'subtypes.json'
    yield 'types.json'

def all_locales(args, files):
    langs = get_languages(args)
    verbose_print(args, "Processing %s...\n"%langs, 1)

    base_translations_path = os.path.join(args.base_path, "translations")
    for locale_name in langs:
        locale = i18nLocale(locale_name, base_translations_path)
        for f in files:
            yield f

def check_translations(args, locale, fileIterator):
    for en_file_path in fileIterator:
            stats = compare_translations(args, locale, en_file_path)
            if not stats is None:
                stats.print_short(args)

def check_all_locales(args, fileIterator):
    langs = get_languages(args)
    verbose_print(args, "Processing %s...\n"%langs, 1)

    files = list(fileIterator)
    base_translations_path = os.path.join(args.base_path, "translations")
    for locale_name in langs:
        locale = i18nLocale(locale_name, base_translations_path)
        check_translations(args, locale, iter(files))

def check_file_list(args, files):
    base_translations_path = os.path.join(args.base_path, "translations")
    abs_translations_path = os.path.abspath(base_translations_path)
    for f in files:
        abs_f = os.path.abspath(f)
        if abs_f.startswith(abs_translations_path):
            rel_f = os.path.relpath(abs_f, abs_translations_path)
            path = pathlib.Path(rel_f)
            if len(path.parts) < 2:
                verbose_print(args, "WARN: cannot process %s"%f, 0)
                continue
            locale = i18nLocale(path.parts[0], base_translations_path)
            rel_f = "/".join(path.parts[1:])
            check_translations(args, locale, iter([rel_f]))
        else:
            rel_f = os.path.relpath(abs_f)
            check_all_locales(args, iter([rel_f]))




def verbose_print(args, text, minimum_verbosity=0):
    if args.verbose >= minimum_verbosity:
        sys.stdout.write(text)

def main():
    # Initialize global counters for encountered validation errors
    global formatting_errors
    global validation_errors
    formatting_errors = 0
    validation_errors = 0

    args = parse_commandline()

    cycles = load_cycles(args)

    packs = load_packs(args, cycles)

    if cycles and packs:
        if len(args.i18n_files) == 0:
            check_all_locales(args, all_files(args))
        else:
            verbose_print(args, "i18_files: %s\n"%args.i18n_files, 0)
            check_file_list(args, args.i18n_files)
    else:
        verbose_print(args, "Skipping card validation...\n", 0)

    sys.stdout.write("Found %s formatting and %s validation errors\n" % (formatting_errors, validation_errors))
    if formatting_errors == 0 and validation_errors == 0:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()


