<%@ taglib uri="http://java.sun.com/jsp/jstl/core" prefix="c"%>
<%@ page session="false"%>
<html>
<head>
<title>Login</title>

<!-- Standard Meta -->
<meta charset="utf-8" />
<meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">

<!--
		Used for including CSRF token in JSON requests
		Also see bottom of this file for adding CSRF token to JQuery AJAX requests
	-->
<meta name="_csrf" content="${_csrf.token}" />
<meta name="_csrf_header" content="${_csrf.headerName}" />

<link href="<c:url value="/resources/semantic/semantic.min.css" />" rel="stylesheet" type="text/css" />
<script type="text/javascript" src="<c:url value="/resources/jquery/2.1.4/jquery.js" />"></script>
<script type="text/javascript" src="<c:url value="/resources/semantic/semantic.min.js" />"></script>


<style type="text/css">
body>.grid {
	height: 100%;
}

.column {
	max-width: 450px;
}
</style>


</head>
<body>
	<div class="ui middle aligned center aligned grid">

		<div class="column left aligned grid">
			<form class="ui large form" action="<c:url value="/j_spring_security_check" />" method="post" role="form">
				<div class="ui stacked segment ">
					<h2 class="ui green header">Log-in to your account</h2>
					<div class="field">
						<label for="j_username">User Name</label>
						<div class="ui icon input">
							<input placeholder="Username" name="j_username" type="text"> <i class="user icon"></i>
						</div>
					</div>
					<div class="field">
						<label>Password</label>
						<div class="ui icon input">
							<input placeholder="Password" name="j_password" type="password"> <i class="lock icon"></i>
						</div>
					</div>

					<div class="ui buttons">
						<div class="ui positive submit button">
							<i class="sign in icon"></i>Login
						</div>
						<div class="or"></div>
						<div class="ui  button">
							<i class="erase icon"></i>Reset
						</div>
					</div>
				</div>
			</form>

			<div class="ui message">
				New to us? <a href="#">Sign Up</a>
			</div>
		</div>
	</div>

	<script>
		$('.ui form').form({
			inline : true,
			on : 'blur',
			transition : 'fade down',
			onSuccess : validationpassed,
			fields : {
				j_username : {
					identifier : 'j_username',
					rules : [ {
						type : 'empty',
						prompt : 'Please enter your user id.'
					} ]
				},
				j_password : {
					identifier : 'j_password',
					rules : [ {
						type : 'empty',
						prompt : 'Please enter your password.'
					}, {
						type : 'length[6]',
						prompt : 'Your password must be at least 6 characters.'
					} ]
				}
			}
		});

		function validationpassed() {

			// Multiple instances may have been bound to the form, only submit one.
			// This is a workaround and not ideal. 
			// Improvements welcomed. 

			if (window.lock != "locked") {
				var myform = $('.ui.form');
				$.ajax({
					type : myform.attr('method'),
					url : myform.attr('action'),
					data : myform.serialize(),
					beforeSend: function (xhr) {
				        xhr.setRequestHeader("X-Ajax-call", "true");
				    },
					success : function(data) {
						alert("Response came as ok" + data);
						window.lock = "";
						if (data == "ok") {
				         alert("Response came as ok");
				        }
						
					}
				});
			}
			window.lock = "locked";
		}

		// stop the form from submitting normally 
		$('.ui.form').submit(function(e) {
			e.preventDefault(); //usually use this, but below works best here.
			return false;
		});
	</script>
</body>
</html>