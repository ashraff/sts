import java.lang.System as System
import os
from ConfigParser import ConfigParser

def fileExists(f):
	try:
		file = open(f)
	except IOError:
		print "ERROR: File " + f + " is missing. Please check and rerun the script..\n"
		sys.exit(1)
	else:
		print "*****File " + f + " Exists *******"
		return 1

if (fileExists("common-was-utils.py")):
	execfile('common-was-utils.py')

print "\n***** Creating WebSphere configurations *****"


createSharedLibrariesForCluster('AMA','AMA_AP_CONFIG','/export/opt/applications/ama/config/ap');
createSharedLibrariesForCluster('AMA','AMA_CP_CONFIG','/export/opt/applications/ama/config/cp');
createSharedLibrariesForCluster('AMA','AMA_FM_CONFIG','/export/opt/applications/ama/config/fm');
createSharedLibrariesForCluster('AMA','AMA_MODULE_LIB','/export/opt/applications/ama/module_lib');
setupEnvironmentEntryForClone('AMA_clone1','AMA_LOG_PATH','/export/opt/applications/ama/logs/C1');
setCloneSDKtoJava8('AMA_clone1');
print "\n***** Saving WebSphere configurations *****"
AdminConfig.save()
