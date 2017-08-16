#!/bin/bash
$PYTHON build.py
mkdir -p $CONDA_PREFIX/share/whitebox_tools # TODO: remove -p
cp -av target/release $CONDA_PREFIX/share/whitebox_tools
$PYTHON setup.py install

ACTIVATE_DIR=$PREFIX/etc/conda/activate.d
DEACTIVATE_DIR=$PREFIX/etc/conda/deactivate.d
mkdir -p $ACTIVATE_DIR $DEACTIVATE_DIR
cat > $ACTIVATE_DIR/whitebox_tools-activate.sh <<EOF
echo export WHITEBOX_TOOLS_BUILD=$CONDA_PREFIX/share/whitebox_tools
export WHITEBOX_TOOLS_BUILD=$CONDA_PREFIX/share/whitebox_tools
EOF
cat > $DEACTIVATE_DIR/whitebox_tools-deactivate.sh <<EOF
echo unset WHITEBOX_TOOLS_BUILD
unset WHITEBOX_TOOLS_BUILD
EOF
