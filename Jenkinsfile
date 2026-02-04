pipeline {
    agent any

    environment {
        ECR_URL = '043187663485.dkr.ecr.ap-south-1.amazonaws.com/smartcart'
        FRONTEND_ECR_URL = '043187663485.dkr.ecr.ap-south-1.amazonaws.com/smartcart-frontend'
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10')) // Keep last 10 builds
        timeout(time: 10, unit: 'MINUTES') // Fail if exceeds 5 min
        disableConcurrentBuilds() // Prevent parallel builds
        timestamps() // Add timestamps to console output
    }

    stages {

        stage('Version Calculation') {
            when { branch 'main' }
            steps {
                withCredentials([usernamePassword(credentialsId: 'GitLab PAT', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_TOKEN')]) {
                    script {
                        sh "git fetch https://\${GIT_USER}:\${GIT_TOKEN}@gitlab.com/arielgabai/smartcart.git --tags"
                        def latestTag = sh(script: 'git tag --sort=-v:refname | head -1', returnStdout: true).trim()
                        def (major, minor, patch) = latestTag.tokenize('.')
                        env.VERSION = "${major}.${minor}.${patch.toInteger() + 1}"
                    }
                }
            }
        }

        stage('Build Docker Image') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                script {
                    env.IMAGE_TAG = env.VERSION ?: 'dev'
                    env.BACKEND_IMAGE = "${ECR_URL}:${env.IMAGE_TAG}"
                    docker.build(env.BACKEND_IMAGE)
                }
            }
        }

        stage('Security Analysis') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            parallel {
                stage('Bandit') {
                    steps {
                        script {
                            docker.image(env.BACKEND_IMAGE).inside {
                                sh 'bandit -r src/ -f json -o bandit.json -c tests/bandit.yaml --severity-level high'
                            }
                        }
                        archiveArtifacts artifacts: 'bandit.json', allowEmptyArchive: true
                    }
                }
                stage('pip-audit') {
                    steps {
                        script {
                            docker.image(env.BACKEND_IMAGE).inside {
                                sh 'pip-audit --format=json -o pip-audit.json'
                            }
                        }
                        archiveArtifacts artifacts: 'pip-audit.json', allowEmptyArchive: true
                    }
                }
                stage('Trivy') {
                    steps {
                        sh "docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image --severity CRITICAL --ignore-unfixed --exit-code 1 --format json ${env.BACKEND_IMAGE} > trivy.json"
                        archiveArtifacts artifacts: 'trivy.json', allowEmptyArchive: true
                    }
                }
            }
        }

        stage('Unit Tests') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                script {
                    docker.image(env.BACKEND_IMAGE).inside {
                        sh 'pytest tests/unit_tests.py --cov=src --cov-report=xml:coverage.xml'
                    }
                }
            }
        }

        stage('SonarCloud Analysis') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                withCredentials([string(credentialsId: 'sonarcloud-token', variable: 'SONAR_TOKEN')]) {
                    script {
                        docker.image('sonarsource/sonar-scanner-cli:latest').inside {
                            sh 'sonar-scanner'
                        }
                    }
                }
            }
        }

        stage('Integration Tests') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_URL}"
                script {
                    env.FRONTEND_IMAGE = "${FRONTEND_ECR_URL}:latest"
                }
                sh "FRONTEND_IMAGE=${env.FRONTEND_IMAGE} BACKEND_IMAGE=${BACKEND_IMAGE} docker compose up -d"

                timeout(time: 2, unit: 'MINUTES') {
                    waitUntil {
                        script {
                            sh(script: 'docker compose exec -T backend curl -sf http://frontend/api/health', returnStatus: true) == 0
                        }
                    }
                }

                script {
                    docker.image(env.BACKEND_IMAGE).inside('--network smartcart_frontend-net') {
                        sh 'pytest tests/integration_tests.py --no-cov'
                    }
                }
            }
        }

        stage('E2E Tests') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                script {
                    docker.image('mcr.microsoft.com/playwright/python:v1.58.0-noble').inside('--network smartcart_frontend-net') {
                        sh 'pip install pytest playwright && TEST_BASE_URL=http://frontend python -m pytest tests/e2e_tests.py -v --tb=short -x -o addopts=""'
                    }
                }
            }
        }

        stage('Tag & Publish') {
            when { branch 'main' }
            parallel {
                stage('Git Tag & Push') {
                    steps {
                        withCredentials([usernamePassword(credentialsId: 'GitLab PAT', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_TOKEN')]) {
                            sh "git tag ${env.VERSION}"
                            sh "git push https://\${GIT_USER}:\${GIT_TOKEN}@gitlab.com/arielgabai/smartcart.git ${env.VERSION}"
                        }
                    }
                }
                stage('Publish to ECR') {
                    steps {
                        sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_URL}"
                        script {
                            def image = docker.image(env.BACKEND_IMAGE)
                            image.push(env.VERSION)
                            image.push('latest')
                        }
                    }
                }
            }
        }

        stage('Deploy to GitOps') {
            when { branch 'main' }
            steps {
                withCredentials([usernamePassword(credentialsId: 'GitLab PAT', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_TOKEN')]) {
                    sh """
                        git clone https://\${GIT_USER}:\${GIT_TOKEN}@gitlab.com/arielgabai/smartcart-gitops.git
                        cd smartcart-gitops
                        sed -i '/repository: 043187663485.dkr.ecr.ap-south-1.amazonaws.com\\/smartcart\$/{ n; s/tag: ".*"/tag: "${env.VERSION}"/; }' smartcart/values.yaml
                        git config user.email "jenkins@ariel.com"
                        git config user.name "Ariel's Jenkins Bot"
                        git add smartcart/values.yaml
                        git commit -m "update backend image to ${env.VERSION}"
                        git push https://\${GIT_USER}:\${GIT_TOKEN}@gitlab.com/arielgabai/smartcart-gitops.git main
                    """
                }
            }
        }
    }

    post {
        always { // Cleanup
            sh 'docker compose down -v --remove-orphans || true'
            sh 'docker system prune -af --volumes || true'
            cleanWs()
            script { // Slack Notification
                def colors = [SUCCESS: 'good', FAILURE: 'danger', ABORTED: 'warning']
                def version = env.VERSION ?: 'dev'
                slackSend(
                    color: colors[currentBuild.result] ?: 'warning', message: "${currentBuild.result}: ${env.JOB_NAME} #${env.BUILD_NUMBER} (${version})"
                )
            }
        }
    }
}
