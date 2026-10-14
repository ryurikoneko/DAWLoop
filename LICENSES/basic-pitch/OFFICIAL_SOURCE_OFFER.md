# Native runtime source and notices

ONNX Runtime 1.31.0 is redistributed without binary changes from the official Microsoft PyPI wheel. Its MIT copyright and complete upstream ThirdPartyNotices.txt are included. No DAWLoop changes were made to the three ONNX native files.

The Eigen source used by upstream is supplied in eigen-source.zip under its original notices and MPL-2.0 terms. Upstream dependency pin: https://github.com/microsoft/onnxruntime/blob/v1.31.0/cmake/deps.txt . Associated upstream patches are in eigen-patches/. Eigen source and any covered modifications remain available under MPL-2.0; DAWLoop MIT terms do not restrict those rights. The full ONNX Runtime source and build scripts are available at https://github.com/microsoft/onnxruntime/tree/v1.31.0 . The binary-to-complete-object-file build graph was not independently reproduced.

Microsoft Visual C++ runtime DLLs come unchanged from the licensed maintainer's Visual Studio Community 2026 release Redist directory, with valid Microsoft signatures. The supplied Visual Studio license applies to these Microsoft files separately from DAWLoop's MIT code. These files are not debug/nonredist files. Do not use Microsoft names or marks to endorse derived software. Upstream licenses and notices must be kept with distributions. See https://aka.ms/vs/18/redistribution and https://visualstudio.microsoft.com/license-terms/vs2026-ga-community/ . Maintainer confirmed lawful use and license acceptance on 2026-10-15; no legal personal name is published.

Windows system DLLs are prerequisites supplied by Windows, not copied from this computer. This package uses app-local Microsoft runtime files and does not install a Windows service or system redistributable.

Existing interpreter and audio library notices and corresponding source instructions are in ../desktop-runtime. The Basic Pitch model and libraries keep their own included licenses and notices. Native audit does not certify arbitrary untrusted models; DAWLoop loads only its pinned model hash in an isolated worker. ORT telemetry is disabled before import and again before model initialization.
