    #!/bin/bash

while getopts ":i:o:" opt; do
    case $opt in
        i)
            INPUT_PATH=$OPTARG
            ;;
        o)
            OUTPUT_PATH=$OPTARG
            ;;
    esac
done

if [ -z "${INPUT_PATH}" ]; then
    echo "Missing input path for -i argument"
    exit 1
fi

if [ -z "${OUTPUT_PATH}" ]; then
    echo "Missing output path for -o argument"
    exit 1
fi

WORKDIR=/usr/local/dain-app

docker run -it \
    -v ${INPUT_PATH}:${WORKDIR}/content/input \
    -v ${OUTPUT_PATH}:${WORKDIR}/content/output \
    --gpus all \
    --rm \
    dain-app \
    /bin/bash -c "source activate dain-app && cd /usr/local/dain-app && python run_default_batch.py"