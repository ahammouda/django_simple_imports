.. Django Simple Imports documentation master file, created by
   sphinx-quickstart on Tue Aug 21 12:47:15 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Django Simple Imports
=====================

A data import library for the django ORM.  Allows for richness in foreigkey ('data dependency')
constraint specification for imports, that other libraries struggle with (see prior work).
There are extensive ambitions for this library, but for now aims to simply solve the problem of
bulk importing rows for a single model, given an arbitray depth of depency relationships that
must be maintained/referenced during import.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   Quickstart <quickstart>
   Prior Work <prior>
   Architecture <architecture>
   Class Reference <api_reference>



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`