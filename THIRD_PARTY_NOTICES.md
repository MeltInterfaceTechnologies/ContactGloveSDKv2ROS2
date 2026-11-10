# Third-Party Notices

The C++ SDK runtime bundled with ContactGlove ROS2 SDK V2 includes oscpack.
The first-party SDK portions use Apache-2.0 (LICENSE.md); third-party components
retain their own license terms and are not relicensed here. ROS 2 packages
installed separately carry their own licenses and notices.

## oscpack

- Project: oscpack -- Open Sound Control (OSC) packet manipulation library
- Source: <https://github.com/RossBencina/oscpack>
- Pinned revision: `3e7e3a102e316d75fe176885a6dd08f216f2eac0`
- Local modification: `cmake/PatchOscpack.cmake` generates a patched socket
  implementation at build time to preserve early stop requests, synchronize the
  stop flag, and drain POSIX wake bytes on exit. Upstream source and license
  text remain unchanged.
- License:

```text
oscpack -- Open Sound Control (OSC) packet manipulation library
http://www.rossbencina.com/code/oscpack

Copyright (c) 2004-2013 Ross Bencina <rossb@audiomulch.com>

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files
(the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR
ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

The text above constitutes the entire oscpack license; however,
the oscpack developer(s) also make the following non-binding requests:

Any person wishing to distribute modifications to the Software is
requested to send the modifications to the original developer so that
they can be incorporated into the canonical version. It is also
requested that these non-binding requests be included whenever the
above license is reproduced.
```
