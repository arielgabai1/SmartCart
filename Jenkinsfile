pipeline {
    agent any

    environment {
        ECR_URL = '043187663485.dkr.ecr.ap-south-1.amazonaws.com/smartcart'
        FRONTEND_ECR_URL = '043187663485.dkr.ecr.ap-south-1.amazonaws.com/smartcart-frontend'
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10')) // Keep last 10 builds
        timeout(time: 5, unit: 'MINUTES') // Fail if exceeds 5 min
        disableConcurrentBuilds() // Prevent parallel builds
        timestamps() // Add timestamps to console output
    }

    stages {

        stage('Version Calculation') {
            when { branch 'main' }
            steps {
                script {
                    sh 'git fetch --tags'
                    def latestTag = sh(script: 'git describe --tags --abbrev=0', returnStdout: true).trim()
                    def (major, minor, patch) = latestTag.tokenize('.')
                    env.VERSION = "${major}.${minor}.${patch.toInteger() + 1}"
                }
            }
        }

        stage('Build Docker Image') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                script {
                    env.IMAGE_TAG = env.VERSION ?: 'dev'
                    env.BACKEND_IMAGE = "${ECR_URL}:${env.IMAGE_TAG}"
                    docker.build(env.BACKEND_IMAGE, './backend')
                }
            }
        }

        stage('Unit Tests') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                script {
                    docker.image(env.BACKEND_IMAGE).inside { sh 'cd backend && pytest tests/unit_tests.py' }
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
                        sh 'cd backend && pytest tests/integration_tests.py --no-cov'
                    }
                }
            }
        }

        stage('Git Tag & Push') {
            when { branch 'main' }
            steps {
                withCredentials([usernamePassword(credentialsId: 'GitLab PAT', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_TOKEN')]) {
                    sh "git tag ${env.VERSION}"
                    sh "git push https://\${GIT_USER}:\${GIT_TOKEN}@gitlab.com/arielgabai/smartcart.git ${env.VERSION}"
                }
            }
        }

        stage('Publish to ECR') {
            when { branch 'main' }
            steps {
                sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_URL}"
                script {
                    def image = docker.image(env.BACKEND_IMAGE)
                    image.push(env.VERSION)
                    image.push('latest')
                }
            }
        }   

        stage('Deploy to GitOps') {
            when { branch 'main' }
            steps {
                echo 'TODO: Implement deployment steps here, updating manifests, triggering ArgoCD sync.'
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
