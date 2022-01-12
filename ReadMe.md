# What is motionEye.eo?

motionEye.eo is an online interface for the software [ _motion_ ](https://motion-project.github.io/), a video surveillance program with motion detection.

It's a fork of [ _motionEye_ ](https://github.com/ccrisan/motioneye) with the addition of internationalization.  
The supported languages are:
* French
* Esperanto
* English

The following languages have been translated by machine translation and must be corrected:

* Arabic ( _ﺎﻠﻋﺮﺒﻳﺓ_ )
* Bengal ( _বাংলা)_ )
* German ( _Deutsch_ )
* Hispana ( _Español_ )
* Hindi ( _हिन्दी _ )
* Itala ( _Italiano_ )
* Japan ( _日本語_ )
* Malay ( _ﺐﻫﺎﺳ ﻡﻼﻳﻭ_ )
* Punjab ( _ਪੰਜਾਬੀ _ )
* Portugal ( _Português_ )
* Russian ( _русский язык_ )
* Chinese ( _中文_ )

# Installation :

You need :
* a linux machine (tested only on debian bullseye).
* python3 and python3-pip.
* recommended : python3-tornado ,python3-jinja2 ,python3-pillow ,python3-pycurl ,python3-babel ,python3-numpy ,python3-boto3

```
sudo pip install motioneye.eo
sudo motioneye_init
```

# Upgrade
```
sudo systemctl stop motioneye
sudo pip install motioneye.eo --upgrade
sudo systemctl start motioneye
```

# Documentation
[Clik here to view documentation](https://jmichault.github.io/motioneye.eo-dok/)

