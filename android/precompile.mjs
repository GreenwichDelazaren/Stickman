// Replace a wheel's .py files with compiled .pyc files, by android/build.py:  node precompile.mjs <vendor folder> <wheel>
// Pyodide's numpy has only sources, so without this every start of the app compiles them all again.
// It runs in the same Pyodide the app uses, because compiled Python only loads in the version that made it.
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [vendor, wheel] = process.argv.slice(2);
const { loadPyodide } = await import(pathToFileURL(path.join(vendor, "pyodide.mjs")).href);
const py = await loadPyodide({ indexURL: vendor + path.sep });
const file = path.join(vendor, wheel);
py.FS.writeFile("/in.whl", readFileSync(file));
py.runPython(`
import importlib.util, marshal, sys, zipfile

site = f"/lib/python{sys.version_info[0]}.{sys.version_info[1]}/site-packages/"
with zipfile.ZipFile("/in.whl") as old, zipfile.ZipFile("/out.whl", "w", zipfile.ZIP_DEFLATED) as new:
    for entry in old.infolist():
        name, data = entry.filename, old.read(entry)
        if name.endswith(".py"):
            code = compile(data, site + name, "exec", dont_inherit=True)
            # The header of a .pyc: magic, flags, source time and size (only the magic and flags are
            # looked at when there's no source next to it).
            name, data = name + "c", importlib.util.MAGIC_NUMBER + bytes(12) + marshal.dumps(code)
        new.writestr(name, data)
`);
writeFileSync(file, py.FS.readFile("/out.whl"));
