# asanaFS

asana but in your files


## todo

- support updating task contents
    - impl `AsanaTask.__eq__`
- support renaming tasks
- support creating tasks
- make the caching good and not bad
    - run a background thread for continuously syncing state
        - refresh task listings every 1m
        - refresh task contents every 5m
        - refresh workspaces and projects every 30m
    - add a last_refreshed field to AsanaTask and dumped repr
    - add a last_refreshed file to workspace and project dirs
    - give users a way to force-refresh listings and content
    - faster getattr for listing tasks: if a task isn't already in the cache, return dummy values and set the symlink flag in st_mode (as a shitty way to let the user know the attr data is inaccurate)
- support other auth flows