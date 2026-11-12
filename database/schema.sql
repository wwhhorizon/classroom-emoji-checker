-- MySQL 8.4; all timestamps are UTC.

SET NAMES utf8mb4;

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	username VARCHAR(40) NOT NULL, 
	password_hash VARCHAR(128) NOT NULL, 
	`role` VARCHAR(16) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	active INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (role in ('student','teacher','admin')), 
	UNIQUE (username)
);

CREATE TABLE audit_logs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	actor_id INTEGER, 
	action VARCHAR(60) NOT NULL, 
	detail TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);

CREATE INDEX ix_audit_logs_action ON audit_logs (action);

CREATE TABLE courses (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(100) NOT NULL, 
	teacher_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name, teacher_id), 
	FOREIGN KEY(teacher_id) REFERENCES users (id)
);

CREATE INDEX ix_courses_teacher_id ON courses (teacher_id);

CREATE TABLE login_sessions (
	token_hash VARCHAR(64) NOT NULL, 
	user_id INTEGER NOT NULL, 
	expires DATETIME NOT NULL, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_login_sessions_user_id ON login_sessions (user_id);

CREATE TABLE class_sessions (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	course_id INTEGER NOT NULL, 
	start_at DATETIME NOT NULL, 
	end_at DATETIME NOT NULL, 
	class_name VARCHAR(80) NOT NULL, 
	room VARCHAR(80) NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (end_at > start_at), 
	CHECK (version >= 1), 
	FOREIGN KEY(course_id) REFERENCES courses (id)
);

CREATE INDEX ix_class_sessions_course_id ON class_sessions (course_id);

CREATE INDEX ix_class_sessions_start_at ON class_sessions (start_at);

CREATE TABLE emoji_records (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER, 
	session_id INTEGER NOT NULL, 
	emoji VARCHAR(16) NOT NULL, 
	timestamp DATETIME NOT NULL, 
	source VARCHAR(8) NOT NULL, 
	confidence FLOAT, 
	device_id VARCHAR(80) NOT NULL, 
	model_version VARCHAR(100) NOT NULL, 
	event_id VARCHAR(100), 
	PRIMARY KEY (id), 
	CHECK (emoji in ('happy','neutral','sad','surprised','angry','fearful','disgusted')), 
	CHECK (source in ('MANUAL','AI')), 
	CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)), 
	CHECK (source != 'AI' OR confidence IS NOT NULL), 
	CHECK (source != 'MANUAL' OR user_id IS NOT NULL), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(session_id) REFERENCES class_sessions (id), 
	UNIQUE (event_id)
);

CREATE INDEX ix_emoji_session_time ON emoji_records (session_id, timestamp);

CREATE INDEX ix_emoji_records_timestamp ON emoji_records (timestamp);

CREATE INDEX ix_emoji_records_user_id ON emoji_records (user_id);

CREATE INDEX ix_emoji_records_session_id ON emoji_records (session_id);

CREATE TABLE schedule_users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	session_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	scheduled_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (session_id, user_id), 
	FOREIGN KEY(session_id) REFERENCES class_sessions (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_schedule_users_session_id ON schedule_users (session_id);

CREATE INDEX ix_schedule_users_user_id ON schedule_users (user_id);
