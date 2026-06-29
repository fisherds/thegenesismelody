# thegenesismelody
Website for thegenesismelody.web.app


## Local testing note
Note, instead of firebase serve for local development use...

npx serve public -p 5000


This is due to the large audio file. firebase serve doesn't allow skipping to specific times, but npx serve public -p 5000 allows it.