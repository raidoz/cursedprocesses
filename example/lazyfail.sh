#!/bin/sh
echo "Doing something..."
sleep $1
echo "I meant to fail after $1 seconds..."
exit 1
