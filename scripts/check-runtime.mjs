if (process.versions.node.split('.')[0] !== '24') {
  throw new Error('Node 24 is required. Select the project-local runtime or another Node 24 installation.');
}
console.log(`Runtime: Node ${process.version}`);
