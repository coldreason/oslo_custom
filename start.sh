#!/bin/sh
python setup.py build
python setup.py install

python tests/gptj/gptj_test_pp_inference.py