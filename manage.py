#!/usr/bin/python3
import unittest
import sys

if 'test' in sys.argv:
    loader = unittest.TestLoader()
    tests_dir = 'tests'
    tests = loader.discover(tests_dir)

    runner = unittest.TextTestRunner()
    success = runner.run(tests).wasSuccessful()

    exit(0 if success else 1)
