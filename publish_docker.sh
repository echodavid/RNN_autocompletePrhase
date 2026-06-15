#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 [DOCKERHUB_USERNAME] [REPO_NAME]"
  echo "Builds local images and optionally tags/pushes them to Docker Hub."
  echo "Examples:"
  echo "  $0"
  echo "  $0 myuser"
  echo "  $0 myuser myproject"
  exit 1
}

if [ "$#" -gt 2 ]; then
  usage
fi

LOCAL_BACK_IMAGE="rnn-back:latest"
LOCAL_FRONT_IMAGE="rnn-front:latest"
PUSH=false

if [ "$#" -eq 2 ]; then
  DOCKERHUB_USER="$1"
  REPO_NAME="$2"
  PUSH=true
elif [ "$#" -eq 1 ]; then
  DOCKERHUB_USER="$1"
  REPO_NAME="$(basename "$PWD")"
  PUSH=true
fi

if [ "$PUSH" = true ]; then
  REMOTE_BACK_IMAGE="${DOCKERHUB_USER}/${REPO_NAME}-back:latest"
  REMOTE_FRONT_IMAGE="${DOCKERHUB_USER}/${REPO_NAME}-front:latest"
fi

echo "Building local backend image: ${LOCAL_BACK_IMAGE}"
docker build -f back/Dockerfile -t "$LOCAL_BACK_IMAGE" .

echo "Building local frontend image: ${LOCAL_FRONT_IMAGE}"
docker build -f fron/Dockerfile -t "$LOCAL_FRONT_IMAGE" .

if [ "$PUSH" = true ]; then
  echo "Tagging local images for Docker Hub..."
  docker tag "$LOCAL_BACK_IMAGE" "$REMOTE_BACK_IMAGE"
  docker tag "$LOCAL_FRONT_IMAGE" "$REMOTE_FRONT_IMAGE"

  read -p "Docker Hub password for ${DOCKERHUB_USER}: " -s DOCKERHUB_PASSWORD
  echo
  echo "$DOCKERHUB_PASSWORD" | docker login --username "$DOCKERHUB_USER" --password-stdin

  echo "Pushing images to Docker Hub..."
  docker push "$REMOTE_BACK_IMAGE"
  docker push "$REMOTE_FRONT_IMAGE"

  echo "Docker images pushed successfully:"
  echo "  $REMOTE_BACK_IMAGE"
  echo "  $REMOTE_FRONT_IMAGE"

  docker logout
fi

echo "Local images built:"
echo "  $LOCAL_BACK_IMAGE"
echo "  $LOCAL_FRONT_IMAGE"

if [ "$PUSH" = false ]; then
  echo
  echo "To push these images to Docker Hub, run:"
  echo "  $0 YOUR_DOCKERHUB_USER"
  echo "or"
  echo "  $0 YOUR_DOCKERHUB_USER YOUR_REPO_NAME"
fi
