-- Parameters expected from execution environment:
--   ${CATALOG}
--   ${SCHEMA}

CREATE CATALOG IF NOT EXISTS `${CATALOG}`;
CREATE SCHEMA IF NOT EXISTS `${CATALOG}`.`${SCHEMA}`;

USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;