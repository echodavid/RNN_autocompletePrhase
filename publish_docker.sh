#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 DOCKERHUB_USERNAME REPO_NAME"
  echo "Example: $0 myuser myproject"
  exit 1
}

if [ "$#" -ne 2 ]; then
  usage
fi

DOCKERHUB_USER="$1"
REPO_NAME="$2"
BACK_IMAGE="${DOCKERHUB_USER}/${REPO_NAME}-back:latest"
FRONT_IMAGE="${DOCKERHUB_USER}/${REPO_NAME}-front:latest"

read -p "Docker Hub password for ${DOCKERHUB_USER}: " -s DOCKERHUB_PASSWORD
echo

echo "$DOCKERHUB_PASSWORD" | docker login --username "$DOCKERHUB_USER" --password-stdin

echo "Building backend image: ${BACK_IMAGE}"
docker build -f back/Dockerfile -t "$BACK_IMAGE" .

echo "Building frontend image: ${FRONT_IMAGE}"
docker build -f fron/Dockerfile -t "$FRONT_IMAGE" .

echo "Pushing images to Docker Hub..."
docker push "$BACK_IMAGE"
docker push "$FRONT_IMAGE"

echo "Docker images pushed successfully:"
echo "  $BACK_IMAGE"
echo "  $FRONT_IMAGE"

docker logout
