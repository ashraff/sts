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
		return 1


def toArray(list):
	if len(list) == 0:
		return []

	lineSep = System.getProperty("line.separator")

	return list.split(lineSep)

def toArrayAttr(list):
	if len(list) == 0:
		return []

	# empty list
	if len(list) == 2:
		return []

	# skip leading "[" and trailing "]" characters
	list = list[1:len(list) - 1]

	return list.split(" ")

def getConfigVal(configId, name):
	value = ""
	s     = configId.find("/" + name + "/")

	if s != -1:
		s = s + len("/" + name + "/")
		e = configId.find("/", s)

		if e != -1:
			value = configId[s:e]
		else:
			e = configId.find("|", s)

			if e != -1:
				value = configId[s:e]

	return value

def removeConfigObjs(type, parent = None):
	print "Removing config objects... " + type

	ids = toArray(AdminConfig.list(type, parent))

	for id in ids:
		print id

		AdminConfig.remove(id)

	print "Done."

def validateProperty(configId, propsAttrName, expectedName, expectedVal,
	expectedDesc):

	propsId = toArrayAttr(AdminConfig.showAttribute(configId, propsAttrName))
	found	= 0

	for propId in propsId:
		if (AdminConfig.showAttribute(propId, "name") == expectedName):
			found = 1
			break

	if (found == 1):
		if \
			(AdminConfig.showAttribute(propId, "value") != expectedVal) or \
			(AdminConfig.showAttribute(propId, "description") != expectedDesc):

			print "Modifying property: " + expectedName

			AdminConfig.modify(propId, [\
				["value", expectedVal], \
				["description", expectedDesc]\
			])
	else:
		print "Creating a new property: " + expectedName + ", " + expectedVal

		AdminConfig.create("Property", configId, [\
			["name", expectedName], \
			["value", expectedVal], \
			["description", expectedDesc]\
		])

def getCellName():
	cellId = AdminConfig.list("Cell")

	return AdminConfig.showAttribute(cellId, "name")

def getJMSProviderId(clusterName):
	return AdminConfig.getid("/ServerCluster:" + clusterName + "/JMSProvider:TIBCO EMS PHX/")

def createCluster(clusterName, membersPerNode, disableHttpPorts):
	print "createCluster()... " + clusterName

	AdminTask.createCluster([\
		'-clusterConfig', \
		'[-clusterName ' + clusterName + ' -preferLocal true]', \
		'-replicationDomain', \
		'[-createDomain true]'\
	])

	nodeNames = toArray(AdminTask.listManagedNodes())
	nodeNames.sort()

	i = 1

	for nodeName in nodeNames:
		memberName = ""

		# create "membersPerNode" cluster members per managed node

		for j in range(membersPerNode):
			memberName = clusterName + "_clone" + str(i)

			print "Creating cluster member: (" + nodeName + "/" + \
				memberName + ")..."

			AdminTask.createClusterMember([\
				'-clusterName', clusterName, \
				'-memberConfig', \
				'[-memberNode ' + nodeName + ' -memberName ' + memberName + \
					' -replicatorEntry true]'\
			])

			# optionally, disable all Web Container HTTP ports

			if (disableHttpPorts == 1):
				serverId = AdminConfig.getid("/Node:" + nodeName + \
					"/Server:" + memberName + "/")

				chainsId = toArray(AdminConfig.list("Chain", serverId))

				for chainId in chainsId:
					name = AdminConfig.showAttribute(chainId, "name")

					if (name == "WCInboundDefault"):
						print "Disabling WCInboundDefault transport chain..."

						AdminConfig.modify(chainId, [\
							["enable", "false"]\
						])

					AdminConfig.save()

					for ports in getClustersServersPorts(clusterName,i):

						if ports[0] == "DCS_UNICAST_ADDRESS":
							AdminTask.modifyServerPort(memberName, '[-nodeName ' + nodeName + ' -endPointName ' + ports[0] + ' -host ' + "*" + ' -port ' + ports[1] + ' -modifyShared true]')
						else:
							AdminTask.modifyServerPort(memberName, '[-nodeName ' + nodeName + ' -endPointName ' + ports[0] + ' -host ' + nodeName + ' -port ' + ports[1] + ' -modifyShared true]')


			i += 1

def setupVH(clusterName, webServerPort, Port2):
	print "setupVH()... " + clusterName

	cellId = AdminConfig.list("Cell")

	# create a virtual host "<cluster-name>_host"

	vhName = clusterName + "_host"

	print "Creating virtual host: " + vhName

	vhId = AdminConfig.create("VirtualHost", cellId, [\
		["name", vhName]\
	])

	if (clusterName == "BOBJ_PHOENIX"):
		AdminConfig.create("HostAlias", vhId, [["hostname", getProps("URL_HOST")],["port", "443"]])

	nodeNames = toArray(AdminTask.listManagedNodes())

	for nodeName in nodeNames:
		fqHost = nodeName

		# create VH alias for the local Web server

		print "Creating VH alias: " + fqHost + ":" + str(webServerPort)

		AdminConfig.create("HostAlias", vhId, [\
			["hostname", fqHost],\
			["port", str(webServerPort)]\
		])

		print "Creating VH alias: " + fqHost + ":" + str(Port2)

		AdminConfig.create("HostAlias", vhId, [\
			["hostname", fqHost],\
			["port", str(Port2)]\
		])


		nodeId	  = AdminConfig.getid("/Node:" + nodeName + "/")
		serversId = toArray(AdminConfig.list("Server", nodeId))

		for serverId in serversId:
			cName = AdminConfig.showAttribute(serverId, "clusterName")

			if (cName == clusterName):
				serverName = AdminConfig.showAttribute(serverId, "name")
				targetName = "(" + nodeName + "/" + serverName + ")"

				print targetName

				#
				# Save the state (enabled/disabled) of the Web container default
				# secure and non-secure transport chains for the given server.
				#

				isNonSecurePortEnabled = "false"
				isSecurePortEnabled    = "false"

				chainsId = toArray(AdminConfig.list("Chain", serverId))

				for chainId in chainsId:
					name = AdminConfig.showAttribute(chainId, "name")

					if (name == "WCInboundDefault"):
						isNonSecurePortEnabled = \
							AdminConfig.showAttribute(chainId, "enable")
					elif (name == "WCInboundDefaultSecure"):
						isSecurePortEnabled = \
							AdminConfig.showAttribute(chainId, "enable")

				#
				# Process each end point for the given server and create a
				# virtual host alias if the corresponding Web container
				# transport chain is enabled.
				#

				entriesId = toArray(AdminConfig.list("ServerEntry", nodeId))

				for entryId in entriesId:
					sName = AdminConfig.showAttribute(entryId, "serverName")

					if (sName != serverName):
						continue

					nesId = toArrayAttr(\
						AdminConfig.showAttribute(entryId, "specialEndpoints"))

					for neId in nesId:
						epName = AdminConfig.showAttribute(neId, "endPointName")

						if ((epName == "WC_defaulthost") and \
							(isNonSecurePortEnabled == "true")) or \
							((epName == "WC_defaulthost_secure") and \
							(isSecurePortEnabled == "true")):

							epId   = AdminConfig.showAttribute(neId, "endPoint")
							epPort = AdminConfig.showAttribute(epId, "port")

							print "Creating VH alias: " + fqHost + ":" + epPort

							AdminConfig.create("HostAlias", vhId, [\
								["hostname", fqHost],\
								["port", epPort]\
							])


def setupWASVar(varName, varValue):
	print "setupWASVar()... " + varName + ", " + varValue

	entriesId = toArray(AdminConfig.list("VariableSubstitutionEntry"))
	varExist  = 0

	for entryId in entriesId:
		name  = AdminConfig.showAttribute(entryId, "symbolicName")

		if (name == varName):
			nodeName   = getConfigVal(entryId, "nodes")
			serverName = getConfigVal(entryId, "servers")
			targetName = "(" + nodeName + "/" + serverName + ")"

			if (nodeName != ""):
				# node or server scope

				print "Removing WAS variable " + targetName + ": " + \
					name + "..."

				AdminConfig.remove(entryId)
			else:
				# cell scope

				value = AdminConfig.showAttribute(entryId, "value")

				if (value != varValue):
					print "Modifying WAS variable: " + varName + \
						" (" + varValue + ")..."

					AdminConfig.modify(entryId, [\
						["value", varValue]\
					])

				varExist = 1

	# create the variable in the cell scope if it doesn't exist

	if (varExist == 0):
		vmId = AdminConfig.getid("/Cell:" + getCellName() + "/VariableMap:/")

		print "Creating WAS variable: " + varName + " (" + varValue + ")..."

		AdminConfig.create("VariableSubstitutionEntry", vmId, [\
			["symbolicName", varName], \
			["value", varValue]\
		])

def createCF(providerId, type, name, jndiName, externalJNDIName, authAlias, maxConn):
	cfId = AdminConfig.create("GenericJMSConnectionFactory", providerId, [\
		["type", type],\
		["name", name],\
		["jndiName", jndiName],\
		["externalJNDIName", externalJNDIName]\
	])

	AdminConfig.create("ConnectionPool", cfId, [\
		["maxConnections", maxConn]\
	], "connectionPool")

	AdminConfig.modify(cfId, [\
		["authDataAlias", authAlias]\
	])

	AdminConfig.create("MappingModule", cfId, [\
		["mappingConfigAlias", "DefaultPrincipalMapping"]\
	])

def createOracleXAJDBCProvider(clusterName):
	AdminTask.createJDBCProvider('[-scope Cluster=' + clusterName + ' -databaseType Oracle -providerType "Oracle JDBC Driver" -implementationType "XA data source" -name "Oracle JDBC Driver (XA)" -description "Oracle JDBC Driver (XA)" -classpath ${ORACLE_JDBC_DRIVER_PATH}/ojdbc14.jar -nativePath]')

def createOracleXADataSource(clusterName, name, jndiName, authAlias, cmp, props, poolMinSize, poolMaxSize, cacheSize, newRetryCount = "100"):
	print "createOracleXADataSource()... " + clusterName + ", " + name

	providerId = AdminConfig.getid("/ServerCluster:" + clusterName + "/JDBCProvider:Oracle JDBC Driver (XA)/")

	AdminTask.createDatasource(providerId, [\
		"-name", name, \
		"-jndiName", jndiName, \
		"-dataStoreHelperClassName", "com.ibm.websphere.rsadapter.Oracle10gDataStoreHelper", \
		"-componentManagedAuthenticationAlias", authAlias, \
		"-containerManagedPersistence", cmp, \
		"-xaRecoveryAuthAlias", authAlias, \
		"-configureResourceProperties", props\
	])

	dsId = AdminConfig.getid("/ServerCluster:" + clusterName + "/JDBCProvider:Oracle JDBC Driver (XA)/DataSource:" + name + "/")

	connPoolId = AdminConfig.showAttribute(dsId, "connectionPool")

	print "pool size (min/max): (" + poolMinSize + "/" + poolMaxSize + "), cache size: " + cacheSize

	AdminConfig.modify(dsId, [\
		["statementCacheSize", cacheSize] \
	])

	AdminConfig.modify(connPoolId, [\
		["minConnections", poolMinSize],\
		["maxConnections", poolMaxSize],\
		["testConnection", "true"],\
		["testConnectionInterval", "0"]\
	])

	preTestConfigId = AdminConfig.showAttribute(dsId, "preTestConfig")

	if (preTestConfigId == None):
		preTestConfigId = AdminConfig.create("ConnectionTest", dsId, [])

	AdminConfig.modify(preTestConfigId, [\
		["preTestConnection", "true"]\
	])

	propsSetId = AdminConfig.showAttribute(dsId, "propertySet")

	propsId = toArrayAttr(AdminConfig.showAttribute(propsSetId,
		"resourceProperties"))

	for propId in propsId:
		propName = AdminConfig.showAttribute(propId, "name")

		if (propName == "validateNewConnection"):
			AdminConfig.modify(propId, [\
				["value", "true"]\
			])
		elif (propName == "preTestSQLString"):
			AdminConfig.modify(propId, [\
				["value", "SELECT 1 FROM DUAL"]\
			])
		elif (propName == "validateNewConnectionRetryCount"):
			AdminConfig.modify(propId, [\
				["value", newRetryCount]\
			])
		elif (propName == "validateNewConnectionRetryInterval"):
			AdminConfig.modify(propId, [\
				["value", "3"]\
			])

def createOracleJDBCProvider(clusterName):
	print "createOracleJDBCProvider()... "	+ clusterName

	AdminTask.createJDBCProvider('[-scope Cluster=' + clusterName + ' -databaseType Oracle -providerType "Oracle JDBC Driver" -implementationType "Connection pool data source" -name "Oracle JDBC Driver" -description "Oracle JDBC Driver" -classpath ${ORACLE_JDBC_DRIVER_PATH}/ojdbc14.jar -nativePath]')

def createOracleDataSource(clusterName, name, jndiName, authAlias, cmp, props, poolMinSize, poolMaxSize, cacheSize, newRetryCount = "100"):
	print "createOracleDataSource()... " + clusterName + ", " + name

	providerId = AdminConfig.getid("/ServerCluster:" + clusterName + "/JDBCProvider:Oracle JDBC Driver/")

	AdminTask.createDatasource(providerId, [\
		"-name", name, \
		"-jndiName", jndiName, \
		"-dataStoreHelperClassName", "com.ibm.websphere.rsadapter.Oracle10gDataStoreHelper", \
		"-componentManagedAuthenticationAlias", authAlias, \
		"-containerManagedPersistence", cmp, \
		"-configureResourceProperties", props\
	])

	dsId = AdminConfig.getid("/ServerCluster:" + clusterName + "/JDBCProvider:Oracle JDBC Driver/DataSource:" + name + "/")

	connPoolId = AdminConfig.showAttribute(dsId, "connectionPool")

	print "pool size (min/max): (" + poolMinSize + "/" + poolMaxSize + "), cache size: " + cacheSize

	AdminConfig.modify(dsId, [\
		["statementCacheSize", cacheSize] \
	])

	AdminConfig.modify(connPoolId, [\
		["minConnections", poolMinSize],\
		["maxConnections", poolMaxSize],\
		["testConnection", "true"],\
		["testConnectionInterval", "0"]\
	])

	preTestConfigId = AdminConfig.showAttribute(dsId, "preTestConfig")

	if (preTestConfigId == None):
		preTestConfigId = AdminConfig.create("ConnectionTest", dsId, [])

	AdminConfig.modify(preTestConfigId, [\
		["preTestConnection", "true"]\
	])

	propsSetId = AdminConfig.showAttribute(dsId, "propertySet")

	propsId = toArrayAttr(AdminConfig.showAttribute(propsSetId,
		"resourceProperties"))

	for propId in propsId:
		propName = AdminConfig.showAttribute(propId, "name")

		if (propName == "validateNewConnection"):
			AdminConfig.modify(propId, [\
				["value", "true"]\
			])
		elif (propName == "preTestSQLString"):
			AdminConfig.modify(propId, [\
				["value", "SELECT 1 FROM DUAL"]\
			])
		elif (propName == "validateNewConnectionRetryCount"):
			AdminConfig.modify(propId, [\
				["value", newRetryCount]\
			])
		elif (propName == "validateNewConnectionRetryInterval"):
			AdminConfig.modify(propId, [\
				["value", "3"]\
			])

	return dsId

def setupSSLGroups():
	print "setupSSLGroups()..."

	ids = toArray(AdminConfig.list("ApplicationServer"))

	for id in ids:
		nodeName   = getConfigVal(id, "nodes")
		serverName = getConfigVal(id, "servers")
		targetName = "(" + nodeName + "/" + serverName + ")"

		serverType = AdminTask.getServerType( \
			"[-nodeName " + nodeName + " -serverName " + serverName + "]")

		if (serverName.startswith("CAS_PROV_PHOENIX_clone") or serverName.startswith("CAS_LM_PHOENIX_clone")) :
			print targetName

			s = "(cell):" + getCellName() + ":(node):" + nodeName + \
				":(server):" + serverName + \
				":(endpoint):WC_defaulthost_secure"

			a = 0

			try:
				a = AdminTask.getSSLConfigGroup(['-name', 'WC_defaulthost_secure', '-direction', 'inbound', '-scopeName', s])
			except:
				a = 0

			if (a == 0):
				AdminTask.createSSLConfigGroup('[-name WC_defaulthost_secure -direction inbound -certificateAlias default -scopeName ' + s + ' -sslConfigAliasName MutualAuthSSLSettings -sslConfigScopeName (cell):' + getCellName() + ']')
			else:
				AdminTask.modifySSLConfigGroup('[-name WC_defaulthost_secure -direction inbound -certificateAlias default -scopeName ' + s + ' -sslConfigAliasName MutualAuthSSLSettings -sslConfigScopeName (cell):' + getCellName() + ']')

def enableStarupBeansService():
	print "enableStarupBeansService()..."

	ids = toArray(AdminConfig.list("StartupBeansService"))

	for id in ids:
		nodeName   = getConfigVal(id, "nodes")
		serverName = getConfigVal(id, "servers")
		targetName = "(" + nodeName + "/" + serverName + ")"

		serverType = AdminTask.getServerType( \
			"[-nodeName " + nodeName + " -serverName " + serverName + "]")

		if (serverType == "APPLICATION_SERVER" and serverName.startswith("CAS_PHOENIX_clone")):
			print "enableStarupBeansService for " + targetName

			AdminConfig.modify(id, [\
				["enable", "true"]\
			])

		if (serverType == "APPLICATION_SERVER" and serverName.startswith("CAS_PROV_PHOENIX_clone")):
			print "enableStarupBeansService for " + targetName

			AdminConfig.modify(id, [\
				["enable", "true"]\
			])
		if (serverType == "APPLICATION_SERVER" and serverName.startswith("CAS_LM_PHOENIX_clone")):
			print "enableStarupBeansService for " + targetName

			AdminConfig.modify(id, [\
				["enable", "true"]\
			])

def setupTransactionTimeout():
	print "setupTransactionTimeout()..."

	ids = toArray(AdminConfig.list("TransactionService"))

	for id in ids:
		nodeName   = getConfigVal(id, "nodes")
		serverName = getConfigVal(id, "servers")
		targetName = "(" + nodeName + "/" + serverName + ")"

		serverType = AdminTask.getServerType( \
			"[-nodeName " + nodeName + " -serverName " + serverName + "]")

		if (serverType == "APPLICATION_SERVER"):
			if (serverName.startswith("CAS_PHOENIX_")):
				print targetName
				totalTimeout  = "600"
				maxTimeout    = "600"

				AdminConfig.modify(id, [\
					["totalTranLifetimeTimeout", totalTimeout],\
					["propogatedOrBMTTranLifetimeTimeout", maxTimeout],\
				])
			if (serverName.startswith("CAS_PROV_PHOENIX_")):
				print targetName
				totalTimeout  = "10800"
				maxTimeout    = "10800"
				clientTimeout = "600"

				AdminConfig.modify(id, [\
					["totalTranLifetimeTimeout", totalTimeout],\
					["propogatedOrBMTTranLifetimeTimeout", maxTimeout],\
					["clientInactivityTimeout", clientTimeout],\
				])
				validateProperty(id,'properties','ACCEPT_HEURISTIC_HAZARD','TRUE','heuristic hazard setting for JVM')
			if (serverName.startswith("CAS_LM_PHOENIX_")):
				print targetName
				totalTimeout  = "18000"
				maxTimeout    = "18000"
				clientTimeout = "600"

				AdminConfig.modify(id, [\
					["totalTranLifetimeTimeout", totalTimeout],\
					["propogatedOrBMTTranLifetimeTimeout", maxTimeout],\
					["clientInactivityTimeout", clientTimeout],\
				])

			else:
				continue

def setupWorkManagers():
	print "setupWorkManagers()..."

	id = AdminConfig.getid("/ServerCluster:CAS_PROV_PHOENIX/WorkManagerProvider:WorkManagerProvider/")

	AdminConfig.create("WorkManagerInfo", id, [\
		["name", "cas-batch"], \
		["jndiName", "wm/cas/batch"], \
		["serviceNames", "com.ibm.ws.i18n;security;UserWorkArea;AppProfileService"], \
		["minThreads", "5"], \
		["maxThreads", "35"], \
		["numAlarmThreads", "2"], \
		["threadPriority", "5"], \
		["description", "WorkManager for Batch threads"]\
	])

	id = AdminConfig.getid("/ServerCluster:CAS_LM_PHOENIX/WorkManagerProvider:WorkManagerProvider/")

	AdminConfig.create("WorkManagerInfo", id, [\
		["name", "scheduler"], \
		["jndiName", "wm/scheduler"], \
		["serviceNames", "com.ibm.ws.i18n;security;UserWorkArea;AppProfileService"], \
		["minThreads", "0"], \
		["maxThreads", "5"], \
		["numAlarmThreads", "2"], \
		["threadPriority", "5"], \
		["description", "WorkManager for Scheduler threads"]\
	])

	id = AdminConfig.getid("/ServerCluster:CAS_PHOENIX/WorkManagerProvider:WorkManagerProvider/")

	AdminConfig.create("WorkManagerInfo", id, [\
		["name", "CASWorkManager"], \
		["jndiName", "wm/CASWorkManager"], \
		["serviceNames", "com.ibm.ws.i18n;security;UserWorkArea;AppProfileService"], \
		["minThreads", "0"], \
		["maxThreads", "10"], \
		["numAlarmThreads", "2"], \
		["threadPriority", "5"], \
		["description", "CAS Work Manager"]\
	])

def createSharedLibrariesForCluster(cluster,name,classpath):
	id = AdminConfig.getid("/ServerCluster:"+cluster)
	print id
	sharedLibraryId = AdminConfig.list("Library",id)
	print sharedLibraryId
	if (sharedLibraryId.find(name) < 0):
		print "Creating Shared Library	" + name + " for cluster " + cluster

		id = AdminConfig.getid("/ServerCluster:"+cluster)

		print "Created Shared Library  " + name + " for cluster " + cluster
		AdminConfig.create("Library", id, [["name", name], ["classPath", classpath], ["description", classpath]])
	else:
		print "Shared Library " + name + " exists. Skipping."

def createLPs():
	print "createLPs()..."

	ids = toArray(AdminConfig.list("ApplicationServer"))

	for id in ids:
		nodeName   = getConfigVal(id, "nodes")
		serverName = getConfigVal(id, "servers")
		s	   = AdminConfig.getid("/Cell:" + getCellName() + "/Node:" + nodeName + "/Server:" + serverName + "/")
		mls	   = AdminConfig.list("MessageListenerService", s)
		targetName = "(" + nodeName + "/" + serverName + ")"

		serverType = AdminTask.getServerType( \
			"[-nodeName " + nodeName + " -serverName " + serverName + "]")

		if (serverType == "APPLICATION_SERVER"):
			if (serverName.startswith("CAS_PROV_PHOENIX_")):
				print "Creating the listerner ports for " + serverName
				AdminConfig.create('ListenerPort', mls, [['name', 'ProvInitRequestPort'], ['destinationJNDIName', 'jms/TibcoQ_ProvInitRequest'], ['connectionFactoryJNDIName', 'jms/TibcoXAQCF_PROV'], ['maxRetries', '30']])
				AdminConfig.create('ListenerPort', mls, [['name', 'ProvResponsePort'], ['destinationJNDIName', 'jms/TibcoQ_ProvResponse'], ['connectionFactoryJNDIName', 'jms/TibcoXAQCF_PROV'], ['maxRetries', '30']])
				AdminConfig.create('ListenerPort', mls, [['name', 'ProvUserPurnRequestPort'], ['destinationJNDIName', 'jms/TibcoQ_ProvUserPurnRequest'], ['connectionFactoryJNDIName', 'jms/TibcoXAQCF_PROV'], ['maxRetries', '30']])
				AdminConfig.create('ListenerPort', mls, [['name', 'ProvCascadeInitRequestPort'], ['destinationJNDIName', 'jms/TibcoQ_ProvCascadeInitRequest'], ['connectionFactoryJNDIName', 'jms/TibcoXAQCF_PROV'], ['maxRetries', '30']])
			if (serverName.startswith("CAS_LM_PHOENIX_")):
				print "Creating the listerner ports for " + serverName
				AdminConfig.create('ListenerPort', mls, [['name', 'LmInitRequestPort'], ['destinationJNDIName', 'jms/TibcoQ_LMInitRequest'], ['connectionFactoryJNDIName', 'jms/TibcoXAQCF_LM'], ['maxRetries', '3']])
				AdminConfig.create('ListenerPort', mls, [['name', 'EcifInitRequestPort'], ['destinationJNDIName', 'jms/TibcoQ_EcifInitRequest'], ['connectionFactoryJNDIName', 'jms/TibcoXAQCF_ECIF'], ['maxRetries', '3']])
				AdminConfig.create('ListenerPort', mls, [['name', 'LmProcWindRequestPort'], ['destinationJNDIName', 'jms/TibcoQ_LmProcWindRequest'], ['connectionFactoryJNDIName', 'jms/TibcoXAQCF_LM'], ['maxRetries', '3']])

def createCFs():
	print "createCFs()..."

	## Create connection factory for CAS_PHOENIX cluster
	createCF(getJMSProviderId("CAS_PHOENIX"), 'QUEUE', 'TibcoXAQCF_PROV', 'jms/TibcoXAQCF_PROV', 'cmb.gts.na.cas_161804.gport.XAQueueCF.ssl', "TIBCO EMS PHX", 50)
	createCF(getJMSProviderId("CAS_PHOENIX"), 'QUEUE', 'TibcoXAQCF_AUDIT', 'jms/TibcoXAQCF_AUDIT', 'cmb.gts.na.CAS_161804.mfr.XAQueueCF.ssl', "TIBCO EMS PHX", 50)

	## Create connection factory for CAS_PROV_PHOENIX cluster
	createCF(getJMSProviderId("CAS_PROV_PHOENIX"), 'QUEUE', 'TibcoXAQCF_PROV', 'jms/TibcoXAQCF_PROV', 'cmb.gts.na.cas_161804.gport.XAQueueCF.ssl', "TIBCO EMS PHX", 50)

	## Create connection factories for CAS_LM_PHOENIX cluster
	createCF(getJMSProviderId("CAS_LM_PHOENIX"), 'QUEUE', 'TibcoXAQCF_LM', 'jms/TibcoXAQCF_LM', 'cmb.gts.na.cas_161804.gport.XAQueueCF.ssl', "TIBCO EMS PHX", 50)
	createCF(getJMSProviderId("CAS_LM_PHOENIX"), 'QUEUE', 'TibcoXAQCF_AUDIT', 'jms/TibcoXAQCF_AUDIT', 'cmb.gts.na.CAS_161804.mfr.XAQueueCF.ssl', "TIBCO EMS PHX", 50)
	createCF(getJMSProviderId("CAS_LM_PHOENIX"), 'QUEUE', 'TibcoXAQCF_ECIF', 'jms/TibcoXAQCF_ECIF', 'cmb.gts.na.cas_161804.giw.XAQueueCF.ssl', "TIBCO EMS PHX", 50)
	createCF(getJMSProviderId("CAS_LM_PHOENIX"), 'QUEUE', 'TibcoXAQCF_PROV', 'jms/TibcoXAQCF_PROV', 'cmb.gts.na.cas_161804.gport.XAQueueCF.ssl', "TIBCO EMS PHX", 50)

def createDestinations():
	print "createDestinations()..."

	## Create queues for CAS_PROV_PHOENIX cluster
	AdminConfig.create('GenericJMSDestination', getJMSProviderId("CAS_PROV_PHOENIX"), [['type', 'QUEUE'], ['name', 'TibcoQ_ProvInitRequest'], ['jndiName', 'jms/TibcoQ_ProvInitRequest'], ['externalJNDIName', 'cmb.gts.na.gport_156368.gtsportal.gts.app_provisioning_cas_prov_init_request.queue']])
	AdminConfig.create('GenericJMSDestination', getJMSProviderId("CAS_PROV_PHOENIX"), [['type', 'QUEUE'], ['name', 'TibcoQ_ProvResponse'], ['jndiName', 'jms/TibcoQ_ProvResponse'], ['externalJNDIName', 'cmb.gts.na.gport_156368.gtsportal.gts.app_provisioning_cas_prov_response.queue']])
	AdminConfig.create('GenericJMSDestination', getJMSProviderId("CAS_PROV_PHOENIX"), [['type', 'QUEUE'], ['name', 'TibcoQ_ProvUserPurnRequest'], ['jndiName', 'jms/TibcoQ_ProvUserPurnRequest'], ['externalJNDIName', 'cmb.gts.na.gport_156368.gtsportal.gts.app_provisioning_userpurn_request.queue']])
	AdminConfig.create('GenericJMSDestination', getJMSProviderId("CAS_PROV_PHOENIX"), [['type', 'QUEUE'], ['name', 'TibcoQ_ProvCascadeInitRequest'], ['jndiName', 'jms/TibcoQ_ProvCascadeInitRequest'], ['externalJNDIName', 'cmb.gts.na.gport_156368.gtsportal.gts.app_provisioning_cas_prov_cascade_init_request.queue']])

	## Create queues for CAS_LM_PHOENIX cluster
	AdminConfig.create('GenericJMSDestination', getJMSProviderId("CAS_LM_PHOENIX"), [['type', 'QUEUE'], ['name', 'TibcoQ_LMInitRequest'], ['jndiName', 'jms/TibcoQ_LMInitRequest'], ['externalJNDIName', 'cmb.gts.na.cas_161804.barc_migration_start_process_cas.queue']])
	AdminConfig.create('GenericJMSDestination', getJMSProviderId("CAS_LM_PHOENIX"), [['type', 'QUEUE'], ['name', 'TibcoQ_EcifInitRequest'], ['jndiName', 'jms/TibcoQ_EcifInitRequest'], ['externalJNDIName', 'cmb.gts.na.MDM.cas.feeds']])
	AdminConfig.create('GenericJMSDestination', getJMSProviderId("CAS_LM_PHOENIX"), [['type', 'QUEUE'], ['name', 'TibcoQ_LmProcWindRequest'], ['jndiName', 'jms/TibcoQ_LmProcWindRequest'], ['externalJNDIName', 'cmb.gts.na.cas_161804.barc_migration_feed_request_cas.queue']])

def setupClassLoaders():
	print "setupClassLoaders()..."

	ids = toArray(AdminConfig.list("ApplicationServer"))

	for id in ids:
		nodeName   = getConfigVal(id, "nodes")
		serverName = getConfigVal(id, "servers")
		targetName = "(" + nodeName + "/" + serverName + ")"

		serverType = AdminTask.getServerType( \
			"[-nodeName " + nodeName + " -serverName " + serverName + "]")

		if ((serverType == "APPLICATION_SERVER") and \
			(serverName.startswith("CAS_PHOENIX_"))):

			i = serverName.index("_")
			a = serverName[0:i]

			s = "CAS_PHOENIX_LIB"

			print targetName + ": " + s

			cl = AdminConfig.create("Classloader", id, [\
				["mode", "PARENT_LAST"]\
			])

			AdminConfig.create("LibraryRef", cl, [\
				["libraryName", s]\
			])

def setupJVMs():
	print "setupJVMs()..."

	jvmsId = toArray(AdminConfig.list("JavaVirtualMachine"))

	for jvmId in jvmsId:
		nodeName   = getConfigVal(jvmId, "nodes")
		serverName = getConfigVal(jvmId, "servers")

		serverType = AdminTask.getServerType( \
			"[-nodeName " + nodeName + " -serverName " + serverName + "]")

		targetName = "(" + nodeName + "/" + serverName + ")"

		if (serverType == "DEPLOYMENT_MANAGER"):
			jvmAllArgs = ""
			cp = ""
			bootCp = ""
			hMin = ""
			hMax = ""
			if (serverName == "dmgr"):
				print targetName
				hMin   = "512"
				hMax   = "1024"
				jvmAllArgs = "-XX:NewSize=192m -XX:+UseConcMarkSweepGC -XX:ParallelGCThreads=1 -XX:+DisableExplicitGC -XX:SurvivorRatio=4 -XX:TargetSurvivorRatio=90 -XX:+HeapDumpOnOutOfMemoryError -XX:+PrintGC -XX:+PrintGCDetails -XX:+PrintGCTimeStamps -XX:+PrintTenuringDistribution -XX:+PrintHeapAtGC -XX:+PrintGCApplicationConcurrentTime -XX:+PrintGCApplicationStoppedTime -XX:PermSize=300m -XX:MaxPermSize=512m -XX:+CMSPermGenSweepingEnabled -XX:+CMSClassUnloadingEnabled"

				AdminConfig.modify(jvmId, [\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", ""]\
				])

				AdminConfig.modify(jvmId, [\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", jvmAllArgs]\
				])
		elif (serverType == "NODE_AGENT"):
			jvmAllArgs = ""
			cp = ""
			bootCp = ""
			hMin = ""
			hMax = ""
			if (serverName == "nodeagent"):
				print targetName
				hMin   = "256"
				hMax   = "256"
				jvmAllArgs = "-XX:NewSize=192m -XX:+UseConcMarkSweepGC -XX:ParallelGCThreads=1 -XX:+DisableExplicitGC -XX:SurvivorRatio=4 -XX:TargetSurvivorRatio=90 -XX:+HeapDumpOnOutOfMemoryError -XX:+PrintGC -XX:+PrintGCDetails -XX:+PrintGCTimeStamps -XX:+PrintTenuringDistribution -XX:+PrintHeapAtGC -XX:+PrintGCApplicationConcurrentTime -XX:+PrintGCApplicationStoppedTime -XX:PermSize=300m -XX:MaxPermSize=512m -XX:+CMSPermGenSweepingEnabled -XX:+CMSClassUnloadingEnabled"

				AdminConfig.modify(jvmId, [\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", ""]\
				])

				AdminConfig.modify(jvmId, [\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", jvmAllArgs]\
				])
		elif ((serverType == "APPLICATION_SERVER")):
			targetName = "(" + nodeName + "/" + serverName + ")"

			cp     = ""
			bootCp = ""
			oesjvmargs = ""

			if (serverName.startswith("CAS_PHOENIX_")):

				print "Configuring the JVM arguments for " + targetName

				hMin   = "1024"
				hMax   = "1024"
				jvmAllArgs = "-XX:NewSize=256M -XX:+UseConcMarkSweepGC -XX:ParallelGCThreads=8 -XX:+DisableExplicitGC -XX:SurvivorRatio=4 -XX:TargetSurvivorRatio=90 -XX:+HeapDumpOnOutOfMemoryError -XX:+PrintGCDetails -XX:+PrintGCTimeStamps -XX:PermSize=300m -XX:MaxPermSize=512m -XX:+CMSPermGenSweepingEnabled -XX:+CMSClassUnloadingEnabled -XX:+PrintCommandLineFlags"

				cp = "/export/opt/oes-10gR3/ales32-ssm/websphere-ssm/instance/" + serverName + "/config"
				cp = cp + ":/export/opt/oes-10gR3"
				cp = cp + ":/export/opt/oes-10gR3/ales32-ssm/websphere-ssm/lib/oes.jar"

				if (serverName == "CAS_PHOENIX_clone1"):
					armePort = "9003"
				elif (serverName == "CAS_PHOENIX_clone2"):
					armePort = "9004"

				validateProperty(jvmId, "systemProperties", "LD_PRELOAD_64", "/usr/lib/64/libumem.so", "")
				validateProperty(jvmId, "systemProperties", "com.ibm.ws.runtime.dumpShutdown", "true", "Thread dump at shutdown")
				validateProperty(jvmId, "systemProperties", "ales.RealmName", "CasWssm", "")
				validateProperty(jvmId, "systemProperties", "wles.scm.port", "20005", "")
				validateProperty(jvmId, "systemProperties", "wles.arme.port", armePort, "")
				validateProperty(jvmId, "systemProperties", "wles.config.signer", nodeName, "")
				validateProperty(jvmId, "systemProperties", "log4j.configuration", "file:/export/opt/oes-10gR3/ales32-ssm/websphere-ssm/instance/" + serverName + "/config/log4j.properties", "")
				validateProperty(jvmId, "systemProperties", "log4j.ignoreTCL", "true", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.identityKeyAlias", "wles-ssm", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.identityKeyPasswordAlias", "wles-ssm", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.passwordFile", "/export/opt/oes-10gR3/ales32-shared/keys/password.xml", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.passwordKeyFile", "/export/opt/oes-10gR3/ales32-shared/keys/password.key", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.identityKeyStore", "/export/opt/oes-10gR3/ales32-shared/keys/identity.jceks", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.trustedCAKeyStore", "/export/opt/oes-10gR3/ales32-shared/keys/trust.jks", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.trustedPeerKeyStore", "/export/opt/oes-10gR3/ales32-shared/keys/peer.jks", "")
				validateProperty(jvmId, "systemProperties", "arme.configuration", "/export/opt/oes-10gR3/ales32-ssm/websphere-ssm/instance/" + serverName + "/config/WLESarme.properties", "")
				validateProperty(jvmId, "systemProperties", "ales.blm.home", "/export/opt/oes-10gR3/ales32-ssm/websphere-ssm/instance/" + serverName, "")
				validateProperty(jvmId, "systemProperties", "wles.providers.dir", "/export/opt/oes-10gR3/ales32-ssm/websphere-ssm/lib/providers", "")
				validateProperty(jvmId, "systemProperties", "ales.https.handler", "com.ibm.net.ssl.www2.protocol.https.Handler", "")

				AdminConfig.modify(jvmId, [\
					["classpath" , ""],\
					["bootClasspath" , ""],\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", ""]\
				])

				AdminConfig.modify(jvmId, [\
					["classpath" , cp],\
					["bootClasspath" , bootCp],\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", jvmAllArgs]\
				])
			if (serverName.startswith("SENT_PHOENIX_")):

				print "Configuring the JVM arguments for " + targetName
				hMin   = "1024"
				hMax   = "1024"

				jvmAllArgs = "-XX:+UseConcMarkSweepGC -XX:ParallelGCThreads=8 -XX:SurvivorRatio=4 -XX:+DisableExplicitGC -XX:+HeapDumpOnOutOfMemoryError -XX:+PrintGCDetails -XX:+PrintGCTimeStamps -XX:PermSize=180m  -XX:MaxPermSize=256m  -XX:NewSize=256M -XX:+PrintCommandLineFlags"

				cp = "/export/opt/oes-10gR3/ales32-ssm/websphere-ssm/instance/" + serverName + "/config"
				cp = cp + ":/export/opt/oes-10gR3"
				cp = cp + ":/export/opt/oes-10gR3/ales32-ssm/websphere-ssm/lib/oes.jar"

				if (serverName == "SENT_PHOENIX_clone1"):
					armePort = "9007"
				elif (serverName == "SENT_PHOENIX_clone2"):
					armePort = "9008"

				validateProperty(jvmId, "systemProperties", "LD_PRELOAD_64", "/usr/lib/64/libumem.so", "")
				validateProperty(jvmId, "systemProperties", "com.ibm.ws.runtime.dumpShutdown", "true", "Thread dump at shutdown")
				validateProperty(jvmId, "systemProperties", "ales.RealmName", "CasWssm", "")
				validateProperty(jvmId, "systemProperties", "wles.scm.port", "20005", "")
				validateProperty(jvmId, "systemProperties", "wles.arme.port", armePort, "")
				validateProperty(jvmId, "systemProperties", "wles.config.signer", nodeName, "")
				validateProperty(jvmId, "systemProperties", "log4j.configuration", "file:/export/opt/oes-10gR3/ales32-ssm/websphere-ssm/instance/" + serverName + "/config/log4j.properties", "")
				validateProperty(jvmId, "systemProperties", "log4j.ignoreTCL", "true", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.identityKeyAlias", "wles-ssm", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.identityKeyPasswordAlias", "wles-ssm", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.passwordFile", "/export/opt/oes-10gR3/ales32-shared/keys/password.xml", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.passwordKeyFile", "/export/opt/oes-10gR3/ales32-shared/keys/password.key", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.identityKeyStore", "/export/opt/oes-10gR3/ales32-shared/keys/identity.jceks", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.trustedCAKeyStore", "/export/opt/oes-10gR3/ales32-shared/keys/trust.jks", "")
				validateProperty(jvmId, "systemProperties", "wles.ssl.trustedPeerKeyStore", "/export/opt/oes-10gR3/ales32-shared/keys/peer.jks", "")
				validateProperty(jvmId, "systemProperties", "arme.configuration", "/export/opt/oes-10gR3/ales32-ssm/websphere-ssm/instance/" + serverName + "/config/WLESarme.properties", "")
				validateProperty(jvmId, "systemProperties", "ales.blm.home", "/export/opt/oes-10gR3/ales32-ssm/websphere-ssm/instance/" + serverName, "")
				validateProperty(jvmId, "systemProperties", "wles.providers.dir", "/export/opt/oes-10gR3/ales32-ssm/websphere-ssm/lib/providers", "")
				validateProperty(jvmId, "systemProperties", "ales.https.handler", "com.ibm.net.ssl.www2.protocol.https.Handler", "")

				AdminConfig.modify(jvmId, [\
					["classpath" , ""],\
					["bootClasspath" , ""],\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", ""]\
				])

				AdminConfig.modify(jvmId, [\
					["classpath" , cp],\
					["bootClasspath" , bootCp],\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", jvmAllArgs]\
				])
			if (serverName.startswith("CAS_PROV_PHOENIX_")):
				print "Modifying the JVM args for " + serverName
				cp   = "${APP_CFG_ROOT}/cas-phoenix-prov/prov/config"
				hMin = "1024"
				hMax = "1024"
				tNo  = "3"
				lp   = "524288"

				jvmAllArgs   =	"-XX:NewSize=256M -XX:+UseConcMarkSweepGC -XX:ParallelGCThreads=8 -XX:+DisableExplicitGC -XX:SurvivorRatio=4 -XX:TargetSurvivorRatio=90 -XX:+HeapDumpOnOutOfMemoryError -XX:+PrintGCDetails -XX:+PrintGCTimeStamps -XX:PermSize=300m -XX:MaxPermSize=512m -XX:+CMSPermGenSweepingEnabled -XX:+CMSClassUnloadingEnabled -XX:+PrintCommandLineFlags"

				AdminConfig.modify(jvmId, [\
					["classpath" , ""],\
					["bootClasspath" , ""],\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", ""]\
				])
				AdminConfig.modify(jvmId, [\
					["classpath" , cp],\
					["bootClasspath" , bootCp],\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", jvmAllArgs]\
				])

				validateProperty(jvmId, "systemProperties", "LD_PRELOAD_64", "/usr/lib/64/libumem.so", "")
				validateProperty(jvmId, "systemProperties", "com.ibm.ws.runtime.dumpShutdown", "true", "Thread dump at shutdown")
			if (serverName.startswith("CAS_LM_PHOENIX_")):
				print "Modifying the JVM args for " + serverName
				#cp   = "${APP_CFG_ROOT}/cas-phoenix-prov/legacy-migration/config"
				hMin = "1024"
				hMax = "1024"

				jvmAllArgs   = "-XX:NewSize=256M -XX:+UseConcMarkSweepGC -XX:ParallelGCThreads=8 -XX:+DisableExplicitGC -XX:SurvivorRatio=4 -XX:TargetSurvivorRatio=90 -XX:+HeapDumpOnOutOfMemoryError -XX:+PrintGCDetails -XX:+PrintGCTimeStamps -XX:PermSize=300m -XX:MaxPermSize=512m -XX:+CMSPermGenSweepingEnabled -XX:+CMSClassUnloadingEnabled -XX:+PrintCommandLineFlags"

				AdminConfig.modify(jvmId, [\
					["classpath" , ""],\
					["bootClasspath" , ""],\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", ""]\
				])

				AdminConfig.modify(jvmId, [\
					["classpath" , cp],\
					["bootClasspath" , bootCp],\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", jvmAllArgs]\
				])

				validateProperty(jvmId, "systemProperties", "LD_PRELOAD_64", "/usr/lib/64/libumem.so", "")
				validateProperty(jvmId, "systemProperties", "com.ibm.ws.runtime.dumpShutdown", "true", "Thread dump at shutdown")
			if (serverName.startswith("BOBJ_PHOENIX_")):
				print "Modifying the JVM args for " + serverName
				hMin = "1024"
				hMax = "1024"
				tNo  = "4"

				jvmAllArgs   = "-XX:+UseConcMarkSweepGC -XX:+CMSParallelRemarkEnabled -XX:ParallelGCThreads=4 -XX:+DisableExplicitGC -XX:+PrintClassHistogram -XX:+HeapDumpOnOutOfMemoryError -XX:+PrintGCDetails -XX:+PrintGCTimeStamps -XX:+PrintCommandLineFlags"

				AdminConfig.modify(jvmId, [\
					["classpath" , ""],\
					["bootClasspath" , ""],\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", ""]\
				])

				AdminConfig.modify(jvmId, [\
					["classpath" , cp],\
					["bootClasspath" , bootCp],\
					["verboseModeGarbageCollection", "true"],\
					["initialHeapSize", hMin],\
					["maximumHeapSize", hMax],\
					["genericJvmArguments", jvmAllArgs]\
				])

				validateProperty(jvmId, "systemProperties", "LD_PRELOAD_64", "/usr/lib/64/libumem.so", "")
				validateProperty(jvmId, "systemProperties", "com.ibm.ws.runtime.dumpShutdown", "true", "Thread dump at shutdown")
			else:
				continue

def disableLPInitialState(cluster):
	global AdminConfig
	members = AdminConfig.getid("/ServerCluster:"+cluster+"/ClusterMember:/")
	members = members.split(lineSeparator)
	for member in members:
		serverName = AdminConfig.showAttribute(member, "memberName")
		nodeName = AdminConfig.showAttribute(member, "nodeName")
		mls = AdminConfig.getid("/Server:" + serverName + "/ApplicationServer:/EJBContainer:/MessageListenerService:/")
		lpListUnsplit = AdminConfig.showAttribute(mls, "listenerPorts")
		lpList = (lpListUnsplit[1:len(lpListUnsplit)-1]).split(" ")
		for lp in lpList:
			lpName = AdminConfig.showAttribute(lp, "name")
			st = AdminConfig.showAttribute(lp, "stateManagement")
			state = AdminConfig.showAttribute(st, "initialState")
			if (serverName.startswith("CAS_PROV_PHOENIX_clone2")  and lpName == "ProvResponsePort"):
				print "Server " + serverName + ": ListnerPort " + lpName + " state is: " + state
				AdminConfig.modify(AdminConfig.showAttribute(lp, "stateManagement"), "[[initialState STOP]]")
				print (AdminConfig.showAttribute(lp, "stateManagement"), "[[initialState]]")

def setupEvalultPluginKeyStore():
	print "setupPluginKeyStore()..."

	scopeName = "(cell):" + getCellName()

	ksName = "EvaultKeyStore"
	if (dirExists("/export/opt/applications/psent/cas-phoenix/evault-certs")):
		ksPath = "/export/opt/applications/psent/cas-phoenix/evault-certs/key.p12"
	ksIds  = toArray(AdminTask.listKeyStores())
	found  = 0

	for ksId in ksIds:
		if (AdminConfig.showAttribute(ksId, "name") == ksName):
			found = 1
			break

	if (found == 0):
		# create a key store

		print "Creating a key store: " + ksName

		AdminTask.createKeyStore([\
			'-keyStoreName', ksName, \
			'-keyStoreType', 'PKCS12', \
			'-keyStoreLocation', ksPath, \
			'-keyStorePassword', 'sslevault', \
			'-keyStorePasswordVerify', 'sslevault', \
			'-scopeName', scopeName \
		])

def addMLSCustomProp():
	print "createLPs()..."

	ids = toArray(AdminConfig.list("ApplicationServer"))

	for id in ids:
		nodeName   = getConfigVal(id, "nodes")
		serverName = getConfigVal(id, "servers")
		s	   = AdminConfig.getid("/Cell:" + getCellName() + "/Node:" + nodeName + "/Server:" + serverName + "/")
		mls	   = AdminConfig.list("MessageListenerService", s)
		targetName = "(" + nodeName + "/" + serverName + ")"

		serverType = AdminTask.getServerType( \
			"[-nodeName " + nodeName + " -serverName " + serverName + "]")

		if (serverType == "APPLICATION_SERVER"):
			if (serverName.startswith("CAS_PROV_PHOENIX_")):
				validateProperty(mls, "properties", "MAX.RECOVERY.RETRIES", "1440", "Max Recovery Retries Property")
			if (serverName.startswith("CAS_LM_PHOENIX_")):
				print "Creating the listerner ports for " + serverName
				validateProperty(mls, "properties", "MAX.RECOVERY.RETRIES", "1440", "Max Recovery Retries Property")

def setupWASVariableForClone(cloneName,varName,varValue):
	ids = toArray(AdminConfig.list("ApplicationServer"))

	for id in ids:
		nodeName   = getConfigVal(id, "nodes")
		serverName = getConfigVal(id, "servers")
		s	   = AdminConfig.getid("/Cell:" + getCellName() + "/Node:" + nodeName + "/Server:" + serverName + "/")
		targetName = "(cells/" +getCellName() + "/nodes/"+ nodeName + "/servers/" + serverName + "|variables.xml#VariableMap_1)"

		serverType = AdminTask.getServerType( \
			"[-nodeName " + nodeName + " -serverName " + serverName + "]")

		if (serverType == "APPLICATION_SERVER"):
			if (serverName == cloneName):
					print "Creating WAS variable: " + varName + " (" + varValue + "). for Clone " + targetName
					AdminConfig.create("VariableSubstitutionEntry", targetName, [\
						["symbolicName", varName], \
						["value", varValue]\
					])


def setupEnvironmentEntryForClone(cloneName,varName,varValue):
	ids = toArray(AdminConfig.list("ApplicationServer"))
	for id in ids:
		varExist = 0
		nodeName   = getConfigVal(id, "nodes")
		serverName = getConfigVal(id, "servers")

		serverType = AdminTask.getServerType( \
			"[-nodeName " + nodeName + " -serverName " + serverName + "]")

		if (serverType == "APPLICATION_SERVER"):
			if (serverName == cloneName):
					srvid = AdminConfig.getid('/Server:'+serverName)
					pdef = AdminConfig.list('JavaProcessDef', srvid)
					properties = AdminConfig.list('Property', pdef).splitlines()
					for prop in properties:
						#print 'name = ' + AdminConfig.showAttribute(prop, 'name')
						if(AdminConfig.showAttribute(prop, 'name') == varName):
							varExist = 1

					if(varExist == 0):
						print "Creating Environment Entry: " + varName + " (" + varValue + "). for Clone " +pdef
						AdminConfig.create("Property", pdef, [\
							["name", varName], \
							["value", varValue]\
							])
					else:
						print "Variable " + varName+ " already exists. Exiting.."

def setCloneSDKtoJava8(cloneName):

	ids = toArray(AdminConfig.list("ApplicationServer"))
	for id in ids:
		nodeName   = getConfigVal(id, "nodes")
		serverName = getConfigVal(id, "servers")
		serverType = AdminTask.getServerType( \
			"[-nodeName " + nodeName + " -serverName " + serverName + "]")

		if (serverType == "APPLICATION_SERVER"):
			if (serverName == cloneName):
				print "Switching Server SDK to JAVA 8 for : "+ cloneName
				AdminTask.setServerSDK('[-nodeName '+ nodeName+' -serverName '+cloneName+' -sdkName 1.8_64]')
				print "Switched Server SDK to JAVA 8 " + cloneName
