# JSON Patch chain


A small POC using `ENDFtk` and `jsonpatch` to show how one can make a chain of immutable blocks containing data patches with potential use in nuclear data.


## Requirements

Requires ENDFtk to be compiled for your python version.

Follow the setup from the njoy GitHub [here](https://github.com/njoy/ENDFtk).


`export PYTHONPATH=/path/to/dir/containing/ENDFtk.so`


And install jsonpatch library.

`pip install jsonpatch`


## Example

To test it out run the example using U-235 as below:

```bash
python3 chained.py 92-U-235g.jeff33
```

Look in the newly created `blockchain.json` file, then either change the XS values for MF3, MT1 or simply run against another nuclide i.e. U-238 as below:

```bash
python3 chained.py 92-U-238g.jeff33
```

And see the changes in the blockchain.json file making use of jsonpatch.


## Notes

A very small POC to illustrate and test out the usage of JSON patch and blockchain for nuclear data.

Since it is a POC example, the code is quickly written and the serialization methods are very primitive and expected to be slow for large chains.
