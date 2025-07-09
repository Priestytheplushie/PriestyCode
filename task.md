Your job is to enhance the **PriestyCode IDE**. 

This involves many files, but mainly "code_editor.py", which contains the main code editing logic

There is a list of tasks here, but you must do them not all at once, but one at a timme 

**Task 1**: Expand the standard libraries, and other tooltips, right now, Exceptions, standard libaries, library class members, and many others are missing tooltips and descritpions, add them to make it more complete. We also need more complex snippets for simple python stuff. Also the auto-complete UI could use some improvmenets. feel free to ask and we can dicuss about this. Also we neeed text for user-defined imports and their members, which can just be a general explnation and where the import originated from

**Task 2**: Placeholders 2.0: The placeholder system could use a re-work. you must do the following

1. Add highlighting for the current placeholder, and the other placeholders in the snippet. 
2. Fix these 3 bugs
    2a: auto-braces does not work with the placeholders, causing issues like the second brace/paranthesis appearing at the bottom and kicking you out of snippets
    2b: Code-completions don't work with placeholders at all, causing issues like quitting out and putting code in unexpected areas
    2c: backspace kicks you out of placeholders, when it should let you undo your mistakes.
3. New tab and enter logic. Tab should cycle through placeholders, and enter should "confirm" them, tab will cycle through any non-confirmed placeholder, and when all placeholders are confirmed the snippet will exit, also, escape will always exit you out.

**Task 3**: Add collapseable code blocks and the file path visualizer at the top of the editor, the collapseable code should be like modern IDEs with the arrow down. this was poorly described, so ask me if needed.

**Task 4**: Minimap enhancements, right now, its very basic and ugly, intergrate it better into the UI, and use more specifc code blocks besides big rectangles, and make sure it utilizes syntax highlighting

**Task 5**: improve code preformance, as opening large files causes crashes, this includes minimap, syntax highlighting, and general logic as right now its very laggy

**Task 6**: Intergrate it with the main codebase, "priesty_ide.py" needs settings for the new and old features, as well as other things in the menubar, like refactoring.

This is phase 1, phase 2 will be more in-depth, so be ready

**MAKE SURE THE FOLLOWING**

1. Make sure to not cause any Pylance errors, if theyre caused, resolve them or use #type: ignore to supress them as a LAST RESORT. try to resolve them first and ask FOR PREMISSION to use #type: ignore
2. Make sure to not delete any old functionality, it would cause issues
3. Be careful, the codebase is somewhat fragile at some point 