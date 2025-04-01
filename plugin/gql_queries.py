# Various GraphQL queries for the plugin

## Get info about user's pods & spend
GET_USERINFO_PODS_SPEND = '''
query myself {
  myself {
    clientBalance
    pods {
      id
      adjustedCostPerHr
      lastStatusChange
    }
    currentSpendPerHr
  }
}
'''


## Get info about a pod's extra details
GET_PODINFO_RUNTIME_DETAILS = '''
query pod($input: PodFilter) {
  pod(input: $input) {
    id
    containerDiskInGb
    adjustedCostPerHr
    lastStatusChange
    memoryInGb
    name
    gpuCount
    vcpuCount
    volumeInGb
    volumeMountPath
    runtime {
      uptimeInSeconds
      ports {
        ip
        isIpPublic
        privatePort
        publicPort
        type
      }
    }
    machine {
      gpuDisplayName
      maxDownloadSpeedMbps
      maxUploadSpeedMbps
      dataCenterId
      gpuType {
        memoryInGb
      }
    }
  }
}
'''

## Resume pod
SET_POD_RESUME = '''
mutation podResume($input: PodResumeInput!) {
  podResume(input: $input) {
    name
    gpuCount
    adjustedCostPerHr
    lastStatusChange
    machine {
        gpuDisplayName
        dataCenterId
    }
  }
}
'''

## Pod Stop
SET_POD_STOP = '''
mutation podStop($input: PodStopInput!) {
  podStop(input: $input) {
    lastStatusChange
  }
}
'''

## Pod Id
VARIABLE_POD_ID = {
    'podId': ''
}
