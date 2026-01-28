pipeline {
    agent any

    environment {
        ECR_URL = '043187663485.dkr.ecr.ap-south-1.amazonaws.com/smartcart'
        GITLAB_REPO = 'https://gitlab.com/arielgabai/smartcart.git'
        DOCKER_IMAGE = "${ECR_URL}-backend"
        IMAGE_TAG = "v1.0.${BUILD_NUMBER}"
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10')) // Keep last 10 builds
        timeout(time: 5, unit: 'MINUTES') // Fail if exceeds 5 min
        disableConcurrentBuilds() // Prevent parallel builds
        timestamps() // Add timestamps to console output
    }

    stages {

        stage('Unit Tests') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                // Run unit tests with mocked DB
                sh 'docker compose -f docker-compose.test.yml run --rm smartcart_test pytest tests/unit_test.py -v --no-cov'
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
                sh 'docker build -t ${DOCKER_IMAGE}:${IMAGE_TAG} -t ${DOCKER_IMAGE}:latest ./backend'
            }
        }

        stage('Integration Tests') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                sh 'docker compose down -v --remove-orphans || true'
                sh 'docker compose up -d --build'

                timeout(time: 2, unit: 'MINUTES') {
                    waitUntil {
                        script {
                            def exitCode = sh(script: 'docker compose exec -T backend python -c "import requests; requests.get(\'http://localhost:5000/api/health\', timeout=5)"', returnStatus: true)
                            return exitCode == 0
                        }
                    }
                }

                sh 'docker compose exec -T backend pytest tests/integration_test.py -v --no-cov'
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
