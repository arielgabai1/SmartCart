pipeline {
    agent any

    environment {
        ECR_URL = '043187663485.dkr.ecr.ap-south-1.amazonaws.com/smartcart'
        GITLAB_REPO = 'https://gitlab.com/arielgabai/smartcart.git'
        AWS_REGION = 'ap-south-1'
        BACKEND_IMAGE = "${ECR_URL}-backend"
        FRONTEND_IMAGE = "${ECR_URL}-frontend"
        IMAGE_TAG = "v1.0.${BUILD_NUMBER}"
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10')) // Keep last 10 builds
        timeout(time: 5, unit: 'MINUTES') // Fail if exceeds 5 min
        disableConcurrentBuilds() // Prevent parallel builds
        timestamps() // Add timestamps to console output
    }

    stages {

        stage('Unit Test') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                // Run unit tests in isolated container
                sh 'docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from smartcart_test'
            }
            post {
                always {
                    sh 'docker compose -f docker-compose.test.yml down -v --remove-orphans || true'
                }
            }
        }

        stage('Package') { // Build production Docker images
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                sh '''
                    docker build -f deploy/backend/Dockerfile.k8s -t ${BACKEND_IMAGE}:${IMAGE_TAG} -t ${BACKEND_IMAGE}:latest .
                    docker build -f deploy/frontend/Dockerfile.k8s -t ${FRONTEND_IMAGE}:${IMAGE_TAG} -t ${FRONTEND_IMAGE}:latest .
                '''
            }
        }
    }

    post {
        always { // Cleanup Docker resources
            sh 'docker compose down -v --remove-orphans || true'
            sh 'docker compose -f docker-compose.test.yml down -v --remove-orphans || true'
            sh 'docker network prune -f || true'
            sh 'docker image prune -af || true'

            cleanWs() // Clear workspace

            script { // Send Slack notification
                def colors = [SUCCESS: 'good', FAILURE: 'danger', ABORTED: 'warning']
                slackSend(
                    color: colors[currentBuild.result] ?: 'warning',
                    message: "Pipeline ${currentBuild.result} - ${env.JOB_NAME} #${env.BUILD_NUMBER} (${env.IMAGE_TAG})"
                )
            }
        }
    }
}
