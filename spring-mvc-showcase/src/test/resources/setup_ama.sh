#!/bin/sh

WASHOME=/export/opt/middleware/casbe/WebSphere/85-64

HOSTNAME=`hostname -s | tr "[a-z]" "[A-Z]"`

echo HOSTNAME : $HOSTNAME

if [ -f /var/tmp/AMA_SETUP/scripts/gtsadmin/data/AMA_$HOSTNAME.xml ]; then

	result=`$WASHOME/bin/wsadmin.sh -lang jython -c AdminClusterManagement.checkIfClusterExists\(\"AMA\"\) | tail -1`

	if [ "$result" == "'false'" ]; then

		echo "----------------------------CLUSTER NOT EXISTS..CREATING CLUSTER NOW -----------------------------"

		cd  /var/tmp/AMA_SETUP/scripts/gtsadmin/config/

		cp /dev/null configure.properties

		echo export was_home=$WASHOME > configure.properties
		echo export tools_home=/var/tmp/AMA_SETUP/scripts/gtsadmin >> configure.properties

		cd /var/tmp/AMA_SETUP/scripts/gtsadmin/bin
		chmod +x transform.sh

		./transform.sh AMA_$HOSTNAME.xml

		cd $WASHOME
		DATE=`date +%Y-%m-%d`
		rm WebSphereConfig_$DATE.zip
		./bin/backupConfig.sh WebSphereConfig_$DATE.zip -nostop

		if [ $? -eq 0 ]; then
			cd /var/tmp/AMA_SETUP/scripts/gtsadmin/bin
			chmod +x configureCell.sh

			./configureCell.sh

			if [ $? -eq 0 ]; then
				echo "----------------------------------CLUSTER CREATED SUCCESSFULLY--------------------------------------"
				cd /var/tmp/AMA_SETUP/scripts
				$WASHOME/bin/wsadmin.sh -lang jython -f setup-ama.py
			else
				echo "-----------CLUSTER CREATION FAILED. CHECK WITH STE TEAM AND RUN THE ROLLBACK IF NEEDED.-------------"
			fi

		else
			print "-----------------Backing-up WebSphere Configuration Failed. So Exiting----------------------"
			exit 1
		fi

	else
		echo "---------------------------CLUSTER ALREADY EXISTS..--------------------------------"
		cd /var/tmp/AMA_SETUP/scripts
		$WASHOME/bin/wsadmin.sh -lang jython -f setup-ama.py

	fi

else
	echo "ERROR ********* FILE "  /var/tmp/AMA_SETUP/scripts/gtsadmin/data/AMA_$HOSTNAME.xml " dont exists ****** Exiting..."
	exit 1
fi
