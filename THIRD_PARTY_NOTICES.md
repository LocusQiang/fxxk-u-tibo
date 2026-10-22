# Third-party and asset notices

This file distinguishes the project's license, bundled artwork, and separately installed dependencies. It does not relicense third-party software or grant rights the contributors do not hold.

## Project software

fxxk u tibo is copyright (c) 2026 LocusQiang and is distributed under the [MIT License](LICENSE). Preserve that notice and license when redistributing the software or substantial portions of it.

## Bundled AI-generated artwork

The public distribution contains 28 AI-generated kitchen utensil sprites under `assets/kitchen/sprites/`, their manifest, and the derived contact sheet at `docs/kitchen-contact-sheet.png`.

The contributors offer these assets under MIT **only to the extent they hold rights that can be licensed**. No exclusive copyright, uniqueness, or legal protectability of AI-generated output is claimed. The MIT grant cannot create rights that do not exist or convey third-party rights the contributors do not own. The MIT warranty disclaimer applies to the rights granted. This notice is not a claim that a local archive or generation record establishes legal ownership.

## Runtime dependencies and standalone EXE

The v0.2.0 Windows x64 EXE bundles Python 3.14.3, Tcl/Tk, Pillow 12.2.0,
pystray 0.19.5, six 1.17.0, and Node.js 22.20.0. It is built with
PyInstaller 6.22.3. Complete upstream license files, including Pillow codec
notices and the Node third-party notices, are embedded in the EXE under
licenses/ and supplied separately in the release licenses ZIP. PyInstaller's
license exception permits distribution of the bundled application; it does
not relicense the application or dependencies. pystray is LGPL-3.0; its
exact bundled Python source is included under licenses/pystray-source and is
also available at https://github.com/moses-palmer/pystray/tree/v0.19.5.
Users may modify or replace it and rebuild this application using the included
source and build_exe.py. No technical restriction on that rebuilding is imposed.
six is MIT. Python and Tcl/Tk retain their own upstream licenses.

The source ZIP does not vendor these dependencies; source installation installs
the Python packages separately and requires a separate Node runtime.

## Source installation dependencies

| Component | Role | License and distribution boundary |
| --- | --- | --- |
| Pillow 12.2.0 | Loads and transforms image assets | Installed for source use; bundled in the standalone EXE. Retains its upstream MIT-CMU license and notices. |
| Python 3.11–3.14, including tkinter/Tcl/Tk support | Runtime and Windows overlay UI | Source users install it separately; EXE bundles Python 3.14.3. Python and bundled components retain their respective upstream licenses. |
| Node.js 22+ | Local desktop IPC bridge runtime | Source users install it separately; EXE bundles 22.20.0. Node.js retains its MIT license and notices for included third-party components. |
| pystray 0.19.5 and six 1.17.0 | Windows tray integration | LGPL-3.0 and MIT respectively; installed for source use and bundled in the EXE. |

Pillow 12.2.0's upstream license credits Secret Labs AB, Fredrik Lundh and contributors, and Jeffrey 'Alex' Clark and contributors. Its license is separate from this project's MIT license. Installing a package does not make it part of this project's license grant. If you redistribute dependencies yourself, include the notices required by those dependencies and their included components.

Authoritative references:

- [Pillow 12.2.0 license](https://github.com/python-pillow/Pillow/blob/12.2.0/LICENSE)
- [Python license and component notices](https://docs.python.org/3/license.html)
- [Node.js 22.20.0 license and third-party notices](https://github.com/nodejs/node/blob/v22.20.0/LICENSE)

## Historical resources excluded from this release

Earlier personal experiments used Kenney resources and a Three.js-based rendering path. **Those historical resources, models, renderer, and Three.js dependencies are not included in this public distribution.** The bundled kitchen sprites are the AI-generated assets described above. This notice does not import the licenses of excluded historical resources into the current artwork.

## Product names and integration

Codex and OpenAI names identify the application with which this tool attempts to interoperate. This project is not affiliated with, sponsored by, or endorsed by OpenAI. No Codex application, proprietary code, credentials, or user conversation data is licensed or redistributed by this project.

The use of undocumented local interfaces is a compatibility limitation, not a claim of vendor authorization or stable API support. See [Compatibility](docs/compatibility.md).
