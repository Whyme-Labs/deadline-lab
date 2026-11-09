# External software

The optional independent-target adapter invokes a locally installed nginx binary with its DAV module. nginx is independently authored software. The checkpoint environment reported nginx 1.26.3. Its complete version/configuration output and executable hash are recorded per run.

No nginx source, executable or libraries are redistributed in this package. Use an appropriately obtained local installation. Deadline Lab does not patch nginx or claim its protocol behaviour is a vulnerability.

QNX SDK components, target images, headers and licensing material are not included. Native use requires the user's authorised QNX environment.

All Python code in the workbench uses the standard library. CMake and a local C compiler are required for the portable C fixture. The generated report is standalone HTML without remote scripts or assets.
