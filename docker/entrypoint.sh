#!/bin/bash
set -e

#print statements as they are executed
[[ -n $DEBUG_ENTRYPOINT ]] && set -x

case ${1} in
  app:run)
    #do some validation. We want to make sure that the notifications work
    #make sure the output dir is accessible
    chown ${TRIPLY_USER}:${TRIPLY_USER} ${TRIPLY__PATHS__DATA_DIR}


    #Run the ETL script
    sudo -HEu ${TRIPLY_USER} bash -c "${TRIPLY_HOME}/runEtl"
    ;;

  app:help)
    echo "Available options:"
    echo " app:run            - Runs the etl (default)"
    echo " app:help           - Displays the help"
    echo " [command]          - Execute the specified command, eg. bash."
    ;;
  *)
    exec "$@"
    ;;
esac

exit 0
