// Azure Container Apps plan for the Customer Loyalty and Engagement Assistant.
//
// STATUS: template only. It has NOT been deployed and must not be deployed without
// explicit team approval (billable, public-facing resources). See docs/DEPLOYMENT.md.
//
// Deploy into an existing resource group (after approval):
//   az deployment group create -g <rg> -f infrastructure/azure/main.bicep \
//     -p infrastructure/azure/main.parameters.example.json -p imageTag=<git-sha>
// API keys are passed as secure parameters at deploy time (or Key Vault references),
// never stored in this file, a parameter file, an image or a workflow log.

targetScope = 'resourceGroup'

@description('Azure region; defaults to the resource group location.')
param location string = resourceGroup().location

@description('Short name prefix for all resources (lowercase letters and digits).')
@minLength(3)
@maxLength(12)
param namePrefix string

@description('Name of the existing Azure Container Registry (admin user disabled).')
param acrName string

@description('Immutable image tag, normally the git commit SHA. Never "latest".')
param imageTag string

@description('LLM provider for the backend: anthropic, groq or mock.')
@allowed([
  'anthropic'
  'groq'
  'mock'
])
param llmProvider string = 'mock'

@description('Anthropic API key. Leave empty to run without it (mock mode).')
@secure()
param anthropicApiKey string = ''

@description('Groq API key. Leave empty if Groq is not used.')
@secure()
param groqApiKey string = ''

@description('Deploy the React frontend app as well.')
param deployFrontend bool = true

var tags = {
  project: 'loyalty-assistant'
  managedBy: 'bicep'
}

// AcrPull built-in role definition ID.
var acrPullRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)

var llmSecrets = concat(
  empty(anthropicApiKey) ? [] : [
    {
      name: 'anthropic-api-key'
      value: anthropicApiKey
    }
  ],
  empty(groqApiKey) ? [] : [
    {
      name: 'groq-api-key'
      value: groqApiKey
    }
  ]
)

var llmSecretEnv = concat(
  empty(anthropicApiKey) ? [] : [
    {
      name: 'ANTHROPIC_API_KEY'
      secretRef: 'anthropic-api-key'
    }
  ],
  empty(groqApiKey) ? [] : [
    {
      name: 'GROQ_API_KEY'
      secretRef: 'groq-api-key'
    }
  ]
)

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${namePrefix}-logs'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// The registry is created once beforehand (approved step, see docs/DEPLOYMENT.md) so
// images can be pushed before the apps that pull them are created.
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-acr-pull'
  location: location
  tags: tags
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, pullIdentity.id, acrPullRoleId)
  scope: acr
  properties: {
    principalId: pullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleId
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${namePrefix}-env'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

var registries = [
  {
    server: acr.properties.loginServer
    identity: pullIdentity.id
  }
]

var identityBlock = {
  type: 'UserAssigned'
  userAssignedIdentities: {
    '${pullIdentity.id}': {}
  }
}

// Backend: one replica while on SQLite (EmptyDir volume, reseeded on start; demo only).
resource backend 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-backend'
  location: location
  tags: tags
  identity: identityBlock
  dependsOn: [
    acrPull
  ]
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: registries
      secrets: llmSecrets
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: '${acr.properties.loginServer}/loyalty-assistant/backend:${imageTag}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: concat(
            [
              {
                name: 'LLM_PROVIDER'
                value: llmProvider
              }
              {
                name: 'DATABASE_URL'
                value: 'sqlite:////app/outputs/app.db'
              }
              {
                name: 'CORS_ORIGINS'
                value: 'https://${namePrefix}-frontend.${env.properties.defaultDomain},https://${namePrefix}-reviewer.${env.properties.defaultDomain}'
              }
            ],
            llmSecretEnv
          )
          volumeMounts: [
            {
              volumeName: 'app-data'
              mountPath: '/app/outputs'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/api/health'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/api/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      volumes: [
        {
          name: 'app-data'
          storageType: 'EmptyDir'
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

resource reviewer 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-reviewer'
  location: location
  tags: tags
  identity: identityBlock
  dependsOn: [
    acrPull
  ]
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8501
        transport: 'auto'
        allowInsecure: false
      }
      registries: registries
    }
    template: {
      containers: [
        {
          name: 'reviewer-ui'
          image: '${acr.properties.loginServer}/loyalty-assistant/reviewer-ui:${imageTag}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              // Streamlit calls the backend server-side over HTTPS ingress.
              name: 'API_BASE_URL'
              value: 'https://${backend.properties.configuration.ingress.fqdn}'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/_stcore/health'
                port: 8501
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

resource frontend 'Microsoft.App/containerApps@2024-03-01' = if (deployFrontend) {
  name: '${namePrefix}-frontend'
  location: location
  tags: tags
  identity: identityBlock
  dependsOn: [
    acrPull
  ]
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
        allowInsecure: false
      }
      registries: registries
    }
    template: {
      containers: [
        {
          name: 'frontend'
          // Built with VITE_API_BASE_URL=https://<backend fqdn> (see deploy-azure.yml).
          image: '${acr.properties.loginServer}/loyalty-assistant/frontend:${imageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/'
                port: 8080
              }
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output acrLoginServer string = acr.properties.loginServer
output backendUrl string = 'https://${backend.properties.configuration.ingress.fqdn}'
output reviewerUrl string = 'https://${reviewer.properties.configuration.ingress.fqdn}'
output frontendUrl string = deployFrontend ? 'https://${frontend!.properties.configuration.ingress.fqdn}' : ''
