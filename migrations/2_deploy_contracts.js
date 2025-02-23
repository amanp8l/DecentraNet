// migrations/2_deploy_contracts.js
const PostStorage = artifacts.require("PostStorage");

module.exports = function(deployer) {
  deployer.deploy(PostStorage);
};