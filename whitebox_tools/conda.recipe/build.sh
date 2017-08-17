#!/bin/bash
$PYTHON build.py
mkdir -p $CONDA_PREFIX/share/whitebox_tools
cp -av target/release $CONDA_PREFIX/share/whitebox_tools
$PYTHON setup.py install

# conda-build is finnicky about recursive cp commands
mkdir -p $SP_DIR/whitebox_tools/data
cp -av whitebox_tools/data/* $SP_DIR/whitebox_tools/data

ACTIVATE_DIR=$PREFIX/etc/conda/activate.d
DEACTIVATE_DIR=$PREFIX/etc/conda/deactivate.d
mkdir -p $ACTIVATE_DIR $DEACTIVATE_DIR
cat > $ACTIVATE_DIR/whitebox_tools-activate.sh <<EOF
echo export WHITEBOX_TOOLS_BUILD=$CONDA_PREFIX/share/whitebox_tools/release/
export WHITEBOX_TOOLS_BUILD=$CONDA_PREFIX/share/whitebox_tools/release/
EOF
cat > $DEACTIVATE_DIR/whitebox_tools-deactivate.sh <<EOF
echo unset WHITEBOX_TOOLS_BUILD
unset WHITEBOX_TOOLS_BUILD
EOF