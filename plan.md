PCA Initiative Software
Guardian AI
-AIM
The final software will allow parents to have an end-to-end control over all the smart devices used by their child/children. The Client side of software will gain root level access to the android / IOS / windows / mac device and provide a consented monitoring and control access to the parent in a detailed dashboard.

-MVP target
The first MVP will be built targeting the following.
-	A client-side android application
-	A Backend to receive the client information and present it on parental dashboard.
-	A Frontend of dashboard.
This will primarily provide three features.
-	 Monitoring app-wise and over all screen time of client device and blocking it accordingly.
-	Track live location and show it on dashboard along with notification in case of location going out of allowed region.
-	Monitoring URL calls from device and blocking adult and all kind of content that should not be accessed by a child.

-TECH STACK
Client	Android Studio
Backend - Django
Database - SQLite
Frontend- Django templates

-USER Flow
Child’s Device
•	On installation, the app will offer login option for guardian (sign up only through dashboard)
•	Once logged in, the app will list down all the child account created under him. He will choose to which child that device belong to.
•	The child’s app will include a dashboard displaying analytics such as screen time, blocked applications, restricted websites, and current location data.
•	The app will periodically track and share the device’s location with the parent’s dashboard to ensure real-time monitoring. It will keeping sending all the monitored usage metrics to the backend api endpoint along with the selected child hash.
Parent’s Dashboard
•	On visit, there will be login or sign up options for guardian.
•	The parent dashboard will allow adding multiple child profiles and include a dropdown menu to select which child’s dashboard to view.
•	It will display detailed analytics for each child, including screen time, blocked apps, accessed websites, and live or recent location tracking on a map interface.

