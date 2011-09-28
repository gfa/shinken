# Command format
This is json oriented document.

it looks like:

```javascript
{
  'foo':{
     'name': '--name',
     'type': 'TYPE',
     'default': 'default content',
     'gluesign': 'GLUE'
  }
}
```

TYPE can either from:
* **argument**: will be used as *--argument=content*
* **switch**: a command argument without content like *--switch*
* **environment**: as environment variables

use *gluesign* with type *argument*, GLUE can then be of type:
* *absent* then the behaviour fallback to **space**
* **space**: then a space would be used to glue *--argument* with *content*, looking like *--argument content*
* **equal**: then = sign would be used to glue *--argument* with *content*, looking like *--argument=content*
* *any other value*
