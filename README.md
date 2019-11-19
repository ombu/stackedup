# Stacks [![Build Status](https://travis-ci.com/ombu/stacks.svg?branch=develop)](https://travis-ci.com/ombu/stacks)

Tools to help launch and manage micro-service based applications in AWS using
CloudFormation.

Running tests:

    python -m unittest discover 

Packaged and distribute

    python setup.py sdist bdist_wheel
    python -m twine upload dist/*
