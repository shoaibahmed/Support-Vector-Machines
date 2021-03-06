from sklearn.datasets import load_svmlight_file, dump_svmlight_file
import scipy.sparse
import sklearn.metrics
import numpy
import time
from scatter_qp import QP
import multiprocessing as mp

import shutil
import pickle
import os

# Plotting utils
import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sn
import pandas as pd

DISPLAY_CONFUSION_MATRIX = True
USE_SPARSE_MATRICES = True

pickleDir = './PickleDir'
weightsDir = './Weights'
logFile = open("LogFile.txt", "w")
plotOutputFileName = "Plot"
confMatOutputFileName = "ConfMat"
plotOutputLogFileName = open("plot-log.txt", "w")

trainFileName = "train_30.txt"
validationFileName = "validate_30.txt"
numInputFeatures = 1199856

def parallel(y_entry): 
	# Load the data
	y_entry = int(y_entry)
	fileName = os.path.abspath(os.path.join('./PickleDir', str(y_entry) + '_X.npz'))
	# dataInClass = load_svmlight_file(fileName, n_features=numInputDims, zero_based=True)
	# g1, currentY = dataInClass[0], dataInClass[1]	
	g1 = scipy.sparse.load_npz(fileName)

	# g1 = scipy.sparse.hstack([-g1,-numpy.ones((g1.shape[0],1))])
	g1 = -g1
	g1 = scipy.sparse.csc_matrix(g1)
	# h1 = numpy.array([-1+val.dot(w_bar) for val in g1])
	h1 = g1.dot(w_bar) - 1.0
	h1.shape = (g1.shape[0],1)

	# Shape of the weights will vary based on the number of examples in g1
	weights = QP(g1.shape[1] - 1, g1.shape[0], w_bar, numpy.ones((g1.shape[0], 1), numpy.float32), g1, h1)

	# Discard the sai_i's
	weights = weights[:-g1.shape[0]].reshape(-1, 1)
	if USE_SPARSE_MATRICES:
		weights = scipy.sparse.csc_matrix(weights) # For sparse vectors
		fileName = os.path.abspath(os.path.join('./Weights', 'w_' + str(y_entry) + '.npz'))
		scipy.sparse.save_npz(fileName, weights)
	else:
		fileName = os.path.abspath(os.path.join('./Weights', 'w_' + str(y_entry) + '.npy'))
		numpy.save(fileName, weights)
	# print ("Weight vector computed for class: %d" % (y_entry))
	
print ("Loading dataset")
data = load_svmlight_file(trainFileName, n_features=numInputFeatures, zero_based=True)
X, y = data[0], data[1]
X = scipy.sparse.hstack([X, numpy.ones((X.shape[0], 1), numpy.float32)])
X = X.tocsc()
numInputDims = X.shape[1]

data_val = load_svmlight_file(validationFileName, n_features=numInputFeatures, zero_based=True)
X_val, y_val = data_val[0], data_val[1]
X_val = scipy.sparse.hstack([X_val, numpy.ones((X_val.shape[0], 1), numpy.float32)])
X_val = X_val.tocsc()

print ("Number of input dimensions: %d" % numInputDims)
print ("Train set | X shape: %s | Y shape: %s" % (X.shape, y.shape))
print ("Validation set | X shape: %s | Y shape: %s" % (X_val.shape, y_val.shape))
logFile.write ("Number of input dimensions: %d\n" % numInputDims)
logFile.write ("Train set | X shape: %s | Y shape: %s\n" % (X.shape, y.shape))
logFile.write ("Validation set | X shape: %s | Y shape: %s\n" % (X_val.shape, y_val.shape))

y_entries, y_count = numpy.unique(y, return_counts=True)
print ("Dataset loaded successfully") 

# Create the weight vector files
resumeTraining = False
if os.path.exists(weightsDir):
	print ("Weights directory already exists. Resuming from the last training.")
	# exit (-1)
	weightFileList = os.listdir(weightsDir)
	if len(weightFileList) < len(y_entries):
		print ("Warning: Weights directory cannot be used. Removing previous directory.")
		shutil.rmtree(weightsDir)
		os.mkdir(weightsDir)
	else:
		resumeTraining = True
else:
	print ("Creating new weights directory")
	os.mkdir(weightsDir)

# Compute w_bar and write it to the directory
startingIteration = 0
if resumeTraining:
	weightFileList = os.listdir(weightsDir)
	lastWBarFileName = None	# Find the last w_bar file saved
	for fileName in weightFileList:
		if "w_bar" in fileName:
			if lastWBarFileName is None:
				lastWBarFileName = os.path.abspath(os.path.join(weightsDir, fileName))
			else:
				# Compare the iteration number
				wBarLastIterationNumber = int(lastWBarFileName[lastWBarFileName.rfind('_')+1:lastWBarFileName.rfind('.')])
				wBarCurrentIterationNumber = int(fileName[fileName.rfind('_')+1:fileName.rfind('.')])
				if wBarCurrentIterationNumber > wBarLastIterationNumber:
					lastWBarFileName = os.path.abspath(os.path.join(weightsDir, fileName))

			# Update the stating iteration number
			startingIteration = int(lastWBarFileName[lastWBarFileName.rfind('_')+1:lastWBarFileName.rfind('.')]) + 1

	print ("Loading w_bar from file: %s" % (lastWBarFileName))	
	w_bar = numpy.load(lastWBarFileName)
	print ("Training will resume from iteration # %d" % (startingIteration))
else:
	w_bar = numpy.zeros((X.shape[1], 1), numpy.float32)

# Create class specific pickles
print ("Number of classes found in data file: %d" % y_entries.shape[0])
createClassInstanceFiles = False
if os.path.exists(pickleDir):
	list = os.listdir(pickleDir)
	numFiles = len(list)
	print ("Number of files found in directory: %d" % numFiles)
	if numFiles < y_entries.shape[0]:
		shutil.rmtree(pickleDir)
		createClassInstanceFiles = True
else:
	createClassInstanceFiles = True

if createClassInstanceFiles:
	print ("Creating directory for holding pickle data")
	os.mkdir(pickleDir)

	for i in range(y_entries.shape[0]):
		booleanIndex = y == y_entries[i]
		classX = X[booleanIndex]
		# classY = scipy.sparse.csc_matrix(y[booleanIndex])
		classY = y[booleanIndex]
		fileName = os.path.abspath(os.path.join(pickleDir, str(int(y_entries[i])) + '_X.npz'))
		fileNameY = os.path.abspath(os.path.join(pickleDir, str(int(y_entries[i])) + '_Y.npy'))
		# dump_svmlight_file(classX, classY, f=fileName)
		scipy.sparse.save_npz(fileName, classX)
		numpy.save(fileNameY, classY)
		print ("Class # %d | Class ID: %d | Data shape: %s | Label shape: %s | Output file: %s" % (i, y_entries[i], classX.shape, classY.shape, fileName))

numIterations = 100
trainAccuracy = []
validationAccuracy = []
wBarDifferenceNorm = []
trainPredictions = []
validationPredictions = []
for i in range(startingIteration, numIterations):
	try:
		startingTime = time.time()
		print ("Starting SVM solver for iteration # %d" % i)
		numProcesses = mp.cpu_count() / 2
		print ("Starting %d processes" % numProcesses)
		pool = mp.Pool(processes=numProcesses)
		results = pool.map(parallel, y_entries)
		# parallel(y_entries[0])
		print ("All subproblems solved for the iteration # %d" % i)
		endTime = time.time()
		print ("Time elapsed: %s secs" % (endTime - startingTime))
		logFile.write("Iteration: %d | Time elapsed in computation: %s secs\n" % (i, str(endTime - startingTime)))
		pool.terminate()

		# w' is the combination of the w's found for each class
		# Read all of the saved numpy files to compute the optimal hyperplane
		w_bar_new = numpy.zeros((X.shape[1], 1), numpy.float32)
		
		trainScores = []
		validationScores = []
		for y_entry in y_entries:
			if USE_SPARSE_MATRICES:
				fileName = os.path.abspath(os.path.join('./Weights', 'w_' + str(int(y_entry)) + '.npz'))
				weightVector = scipy.sparse.load_npz(fileName)
			else:
				fileName = os.path.abspath(os.path.join('./Weights', 'w_' + str(int(y_entry)) + '.npy'))
				weightVector = numpy.load(fileName)
			w_bar_new += weightVector

			# Compute the train set outputs
			out = X.dot(weightVector)
			trainScores.append(numpy.squeeze(out.toarray()))

			# Compute the validation set outputs
			out = X_val.dot(weightVector)
			validationScores.append(numpy.squeeze(out.toarray()))

		w_bar_new /= y_entries.shape[0]
		fileName = os.path.abspath(os.path.join(weightsDir, 'w_bar_' + str(i) + '.npy'))
		numpy.save(fileName, w_bar_new)

		# Compute the difference between the new and the old w_bar
		euclidean_norm_w_bar_diff = numpy.linalg.norm(w_bar - w_bar_new)

		# Replace the old w_bar with the new w_bar
		w_bar = w_bar_new

		endTime = time.time()
		print ("Total time elapsed (one iteration): %s secs" % (endTime - startingTime))
		logFile.write ("Iteration: %d | Total time elapsed (one iteration): %s secs\n" % (i, str(endTime - startingTime)))

		# Test the performance of the computed results on the validation set
		trainScores = numpy.array(trainScores).T
		validationScores = numpy.array(validationScores).T
		print ("Train scores shape: %s" % str(trainScores.shape))
		print ("Validation scores shape: %s" % str(validationScores.shape))

		# Get the prediction according to maximum score with a hyper-plane
		predictions_train = numpy.argmax(trainScores, axis=1)
		predictions_val = numpy.argmax(validationScores, axis=1)
		print ("Train predictions shape: %s" % str(predictions_train.shape))
		print ("Validation predictions shape: %s" % str(predictions_val.shape))
		
		for pred_iter in range(predictions_train.shape[0]):
			predictions_train[pred_iter] = y_entries[predictions_train[pred_iter]]
		for pred_iter in range(predictions_val.shape[0]):
			predictions_val[pred_iter] = y_entries[predictions_val[pred_iter]]
		
		accuracy_train = numpy.mean(predictions_train == y)
		accuracy_val = numpy.mean(predictions_val == y_val)
		print ("Accuracy on train set: %f" % accuracy_train)
		print ("Accuracy on validation set: %f" % accuracy_val)
		print ("Euclidean-Norm of change in w_bar: %f" % (euclidean_norm_w_bar_diff))
		logFile.write ("Accuracy on train set: %f\n" % (accuracy_train))
		logFile.write ("Accuracy on validation set: %f\n" % (accuracy_val))
		logFile.write ("Euclidean-Norm of change in w_bar: %f\n" % (euclidean_norm_w_bar_diff))
		plotOutputLogFileName.write("%f %f %f\n" % (accuracy_train, accuracy_val, euclidean_norm_w_bar_diff))

		trainAccuracy.append(accuracy_train)
		validationAccuracy.append(accuracy_val)
		wBarDifferenceNorm.append(euclidean_norm_w_bar_diff)

		trainPredictions.extend(predictions_train)
		validationPredictions.extend(predictions_val)

	except KeyboardInterrupt:
		print ("Program terminated by user!")
		pool.terminate()
		pool.join()
		break

logFile.close()
plotOutputLogFileName.close()

# Plot the figures
fig, ax = plt.subplots()
ax.set_title('Accuracy Plot')
numListElements = len(trainAccuracy)
x = numpy.arange(0, numListElements)
ax.plot(x, trainAccuracy, color='green', label='Train', linewidth=2.0)
ax.plot(x, validationAccuracy, color='blue', label='Test', linewidth=2.0)
ax.legend()

ax.set_xlabel('Iterations')
ax.set_ylabel('Accuracy')
plt.tight_layout()
plt.savefig(plotOutputFileName + "-Accuracy.png", dpi=300)

fig, ax = plt.subplots()
ax.set_title(r'Change in $\overline{W}$')
ax.plot(x, wBarDifferenceNorm, color='red', linewidth=2.0)

ax.set_xlabel('Iterations')
ax.set_ylabel(r'$\Delta\overline{W}$')

plt.tight_layout()
plt.savefig(plotOutputFileName + "-Change.png", dpi=300)
plt.close('all')

if DISPLAY_CONFUSION_MATRIX:
	print ("Plotting confusion matrices")
	def addConfusionMatrix(confMat, fileName):
		df_cm = pd.DataFrame(confMat, range(len(confMat)), range(len(confMat)))
		sn.set(font_scale=1.0) #for label size
		sn.heatmap(df_cm, xticklabels=False, yticklabels=False, cbar=True, annot=False)
		plt.tight_layout()
		plt.savefig(fileName, dpi=300)
		plt.close('all')

	trainConfMat = sklearn.metrics.confusion_matrix(y, trainPredictions)
	validationConfMat = sklearn.metrics.confusion_matrix(y_val, validationPredictions)
	addConfusionMatrix(trainConfMat, confMatOutputFileName + "-Train.png")
	addConfusionMatrix(validationConfMat, confMatOutputFileName + "-Test.png")
