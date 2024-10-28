import setuptools
from setuptools import setup


setup(name='urdhva_base',
      version='1.0',
      description='Code generator & runtime ',
      url='',
      author='Venugopalnaidu Chandra(venu@algofusiontech.com)',
      author_email='',
      license='',
      packages=setuptools.find_packages(),
      package_data={'model': ['*.tx', '*.jinja']},
      install_requires=['fastapi==0.110.0', 'email-validator', 'elasticsearch[async]==8.12.1', 'httpx==0.27.0',
                        'jinja2==3.1.3', 'motor==3.3.2', 'textx==4.0.1', 'uvicorn==0.28.0', 'pydantic-settings==2.2.1',
                        'cryptography==42.0.5', 'sqlalchemy==2.0.29', 'pandas==2.2.3', 'numpy==2.1.1', 'redis==5.0.3',
                        'mangum==0.17.0', 'python-keycloak==3.9.1', 'SQLAlchemy==2.0.29', 'SQLAlchemy-Utils==0.41.2',
                        'asyncpg==0.29.0', 'snakecase==1.0.1', 'pymongo==4.7.3', 'setuptools'],
      zip_safe=False
      )
