#!/bin/bash

sudo docker build -t custom-scheduler .
sudo docker tag custom-scheduler:latest davidhaja/kube-repo:demo2
sudo docker push davidhaja/kube-repo:demo2
sudo docker pull davidhaja/kube-repo:demo2