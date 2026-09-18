#!/usr/bin/env bash
# Build the image and push it to Docker Hub, for a CapRover app that deploys by image name.
#
# Built here rather than on the server: the image carries a Node runtime and two AI CLIs, and
# the VPS has the disk for it but not the appetite for the build. This machine is arm64 and the
# server is not, so it is a cross-build under QEMU -- slow, and the reason a version tag is
# worth reusing rather than rebuilding.
#
# Tags are immutable versions. There is no `latest`: CapRover deploys by image name, and a tag
# whose contents changed underneath it can redeploy to the same string and serve either image
# with nothing to tell them apart. A version per deploy also makes a rollback a choice from a
# list instead of a rebuild.
set -euo pipefail

IMAGE="${TARTIB_IMAGE:-smkamranqadri/tartib}"
PLATFORM="${TARTIB_PLATFORM:-linux/amd64}"
VERSION="${1:-}"

if [ -z "$VERSION" ]; then
  echo "usage: ./deploy.sh vX.Y        e.g. ./deploy.sh v1.0" >&2
  exit 2
fi

if docker manifest inspect "$IMAGE:$VERSION" >/dev/null 2>&1; then
  echo "$IMAGE:$VERSION already exists. Tags are immutable; pick the next version." >&2
  exit 1
fi

echo "building $IMAGE:$VERSION for $PLATFORM"
docker buildx build --platform "$PLATFORM" -t "$IMAGE:$VERSION" --push .

cat <<DONE

Pushed $IMAGE:$VERSION

In CapRover: the app's Deployment tab, "Deploy via ImageName", $IMAGE:$VERSION.
Check afterwards:
  - /api/health answers {"ok":true,...}
  - the session cookie comes back with Secure on it
  - http:// redirects rather than answering 200
DONE
