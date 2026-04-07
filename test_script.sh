#! /bin/bash

DOCKER_NAME=podman # can be changed to docker

# building the image - this file needs to be in same folder as Container file
sudo ${DOCKER_NAME} build --target test --tag mytesttool .

NUMBER=1
REFERENCE_FILE=./references/report
TEST_FILE=./tests/reports/report
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color (reset)

mkdir -p tests/reports

# running tests
sudo ${DOCKER_NAME} run --rm -v ./tests:/opt/tests mytesttool \
    -r -o "/opt/${TEST_FILE}_1.json" /opt/tests

sudo ${DOCKER_NAME} run --rm -v ./tests:/opt/tests mytesttool \
    -o "/opt/${TEST_FILE}_2.json" /opt/tests

sudo ${DOCKER_NAME} run --rm -v ./tests:/opt/tests mytesttool \
    -r -o "/opt/${TEST_FILE}_3.json" --dry-run /opt/tests

# filtering tests
sudo ${DOCKER_NAME} run --rm -v ./tests:/opt/tests mytesttool \
    -r -o "/opt/${TEST_FILE}_4.json" -i BLOCKS /opt/tests

sudo ${DOCKER_NAME} run --rm -v ./tests:/opt/tests mytesttool \
    -r -o "/opt/${TEST_FILE}_5.json" -ic BLOCKS -e test_block_result /opt/tests

sudo ${DOCKER_NAME} run --rm -v ./tests:/opt/tests mytesttool \
    -r -o "/opt/${TEST_FILE}_6.json" -it hello_world  /opt/tests

sudo ${DOCKER_NAME} run --rm -v ./tests:/opt/tests mytesttool \
    -r -o "/opt/${TEST_FILE}_7.json" -i BLOCKS -et test_block_result  /opt/tests

echo "---------------------------------------------------------------------"

# test check
while [ -f "${TEST_FILE}_${NUMBER}.json" ]; do
    if diff "${TEST_FILE}_${NUMBER}.json" "${REFERENCE_FILE}_${NUMBER}.json" > /dev/null; then
        echo -e "${NUMBER}. test passed [${GREEN}PASSED${NC}]"
    else
        echo -e "${NUMBER}. test failed [${RED}FAILED${NC}], see ${TEST_FILE}_${NUMBER}.json"
    fi
    ((NUMBER++))
done
