from distutils.core import setup
setup(name='playernsd',
  version="0.0.1",
  package_dir={'playernsd': 'src/playernsd'},
  packages=['playernsd'],
  data_files=[('bin', ['playernsd'])]
  )
