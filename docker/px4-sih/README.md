# PX4 SIH verification image

This is the reproducible source-build runtime for COUP Drone Alpha. It pins the dereferenced PX4 `v1.17.0` commit (`d6f12ad1c4f70ad3230afd7d86e971421e02fef4`) and the official builder image digest.

Build and record the resulting immutable image digest before using it for a verified COUP run:

```powershell
docker build --tag coup-px4-sih:v1.17.0 docker/px4-sih
docker image inspect coup-px4-sih:v1.17.0 --format '{{index .RepoDigests 0}}'
```

The launcher passed to COUP must use that digest, for example:

```powershell
docker run --rm -p 14540:14540/udp -p 14550:14550/udp coup-px4-sih@sha256:<built-image-digest>
```

The source build is intentionally separate from generated per-project overlays. The COUP artifact stores its configuration and evidence; it does not copy PX4 into every project.
