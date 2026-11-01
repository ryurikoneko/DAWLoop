# Desktop Alpha 第三方组件 / Third-party components

DAWLoop application source remains MIT. These notices apply to third-party files only. Original license texts, copyright notices and package/file SHA-256 inventories are retained in this directory and in the installed component. Brand policies remain separate.

## Included components

- Electron 44.6.0 (Chromium 152.0.7977.130, Node 24.21.0): Electron MIT and the complete `LICENSES.chromium.html` at the portable root. React, React DOM, scheduler, i18next and react-i18next retain their MIT notices in `licenses/`.
- Official CPython 3.14.8 Windows x64 embedded distribution: PSF license and original bundled licenses. `python-official.spdx.json` records upstream versions; upstream NOASSERTION is not a license grant. Additional original native notices are included here for OpenSSL, Expat, HACL, libffi, bzip2, mpdecimal, Tcl/Tk, libtommath, xz, zlib-ng and zstd. SQLite is public domain. Tcl/Tk information does not imply that a Python GUI is provided.
- 28 Basic DSP Python dependencies and 262 native files are individually indexed in `basic-audio-sbom.json`. Upstream license texts are copied under `basic-audio/`; installed packages retain their originals. NumPy/SciPy OpenBLAS notices and the GCC Runtime Library Exception are preserved. LLVM uses Apache-2.0 with LLVM exceptions; its notice is retained with llvmlite. Certifi's MPL-covered Python and certificate source files are provided in the component itself. No proprietary music or model weights are included.
- Microsoft release runtime DLLs remain unmodified and retain valid Microsoft signatures. Distribution is under the applicable Visual Studio distributable list and terms, not MIT. The runtime's end-user terms alone do not grant redistribution rights. The included Visual Studio Community / Build Tools terms and official distributable lists explain the applicable distribution permission. No debug runtime, IDE or system installer is included.

Official Microsoft lists: https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution and https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution . Original terms: https://visualstudio.microsoft.com/license-terms/ . The distributor has installed licensed release Visual Studio tools. The end-user terms protect only Microsoft components and do not restrict independently licensed application or LGPL source.

## LGPL corresponding source and rebuilding

The `DAWLoop-0.5.6-alpha.1-Corresponding-Source.zip` release asset provides:

- Complete soxr 1.1.0 sdist, including the bundled libsoxr source, LGPL text and build scripts. It can be rebuilt using its original pyproject build configuration and a Windows compiler.
- libsndfile 1.2.2 official source and exact CMake options. The Alpha DLL is compiled from this source with external codecs and MPEG disabled. This avoids redistributing the previous vendor DLL's unfrozen codec build. WAV/AIFF/native PCM analysis is available; this pack does not supply MP3/FLAC analysis codecs. Original files are never converted or modified. Electron preview support is independent.
- Chromium FFmpeg at `2b68d2babae73714846961fb0ee47e3b3d2e39a9`, full source/configuration and Electron 44.6.0 source including patches/build files. The supplied Windows Chrome configuration disables GPL components. See Electron's source build instructions to rebuild the replaceable `ffmpeg.dll`.
- The application source is publicly available at the release tag. For modified LGPL libraries, rebuild the library, update the explicit native source recipe/file hashes, and rebuild the component/app using the public tools. The hash guards remain enabled; a rebuilt package can include the modified library. No prohibition on reverse engineering for debugging LGPL modifications is imposed by DAWLoop. Microsoft restrictions apply only to Microsoft's own unmodified runtime.

An exact application snapshot is available under `v0.5.6-alpha.1`; the Runtime main branch alone is not the Desktop build source. The source recipe fixes every official wheel/interpreter URL and SHA. `tools/build-wheel-audio-pack.py` rejects missing, extra or changed files and requires explicit native replacement hashes. `tools/build-portable.mjs` requires the component hash, locked tools and clean source.

## Security and scope

Basic DSP uses Python 3.14.8, OpenSSL 3.5.9 and SQLite 3.50.4. This is a tested compatibility baseline, not a guarantee that no vulnerability exists. Existing Basic Pitch installations can still use their verified older Python environment; the Alpha disables first installation of that legacy 3.11.9 dependency stack. No such interpreter, TensorFlow environment or model cache is bundled. Advanced models remain optional and have separate licenses and hardware constraints.

The portable binary is unsigned. Clean Windows compatibility has not been independently verified; the maintainer explicitly accepts this Alpha release uncertainty. Public Windows update notification approval remains disabled. No FL Studio Controller, AutoMix execution, host writes or system services are installed.
