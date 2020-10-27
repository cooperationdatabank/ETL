#!/bin/bash
#exit on any error
set -e


adduser --disabled-login --gecos 'Triply' "${TRIPLY_USER}"
passwd -d "${TRIPLY_USER}"

#make sure home dir and direct sub dirs are owned by triply user.
#(doesnt have to be the case, if we already copied some files or created some volumes
#before running this command)
#Doing a `-R` here as this dir doesnt contain anything large yet anyway (otherwise it would become slow)
chown -R ${TRIPLY_USER}:${TRIPLY_USER} ${TRIPLY_HOME}
