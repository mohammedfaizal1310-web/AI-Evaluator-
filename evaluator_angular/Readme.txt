PROJECT SETUP GUIDE – FRONTEND (ANGULAR)

----------------------------------------
PROJECT OVERVIEW
----------------------------------------
This is an Angular-based frontend application.

Angular Version: 17.3.x
Current Development Node Version: 22.x
Package Manager: npm

----------------------------------------
IMPORTANT NOTE
----------------------------------------
This project is developed using Node.js v22.

However, Angular 17 officially supports:
- Node.js 18 LTS
- Node.js 20 LTS

If you face any issues while running the project, please switch to Node 18 or Node 20.

----------------------------------------
PREREQUISITES
----------------------------------------
1. Install Node.js (v22 OR v18/v20 recommended fallback)
   https://nodejs.org/

2. Install Angular CLI globally:
   npm install -g @angular/cli

----------------------------------------
SETUP INSTRUCTIONS
----------------------------------------
1. Open terminal in the project folder

2. Install dependencies:
   npm install

3. Run the application:
   ng s --o

   OR

   ng serve --open

----------------------------------------
APPLICATION ACCESS
----------------------------------------
The app will open automatically in your browser.

Default URL:
http://localhost:4200/

----------------------------------------
IMPORTANT NOTES
----------------------------------------
- node_modules is not included in this package
- It will be installed using "npm install"
- If errors occur, switch Node version to 18 or 20

----------------------------------------
TROUBLESHOOTING
----------------------------------------
If the project does not run:

1. Check Node version:
   node -v

2. If using Node 22 and facing issues:
   → Install Node 18 or 20

3. Reinstall dependencies:
   npm install

----------------------------------------
DONE
----------------------------------------
The application should now run successfully.