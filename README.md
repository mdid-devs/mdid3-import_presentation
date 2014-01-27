mdid3-import_presentation
=========================

a management command that will move presentations from one server to another

### Installation

In mdid/rooibos/apps - 

```git clone git@github.com:mdid-devs/mdid3-import_presentation.git import_presentation````

Add ```'apps.import_presentation',``` to INSTALLED_APPS in settings_local

```
    INSTALLED_APPS = (
        'apps.import_presentation',
        # 'apps.add_users_from_json',
        'debug_toolbar',
    )
    
```
